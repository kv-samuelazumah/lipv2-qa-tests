"""Configured VAT exclusion: expected outcomes and verifier unit tests."""
import copy
import unittest
from unittest.mock import Mock

import gevent
from gevent.event import Event

from performance.common import WorkerScenario, percentile
from performance.setup.configured_tax_exclusion import (
    EXPECTED, FIXTURE, LOOKUP_HASH, prepare, verify, verify_pipeline,
)


class TaxExclusionRun(WorkerScenario):
    fixture = FIXTURE
    run_prefix = "vat"
    metric_name = "VAT"
    database_check_name = "no_matching_lookup_after"
    prepare = staticmethod(prepare)
    verify_after = staticmethod(verify)

    def validate(self, kind, body, expected):
        super().validate(kind, body, expected)
        for key, value in {"categoryCode": "-1000", "categoryTier": "SEGMENT"}.items():
            if body.get(key) != value:
                raise AssertionError(f"{kind}: expected {key}={value!r}, received {body.get(key)!r}")
        if kind == "result":
            # The worker uses OPENAI for every coded outcome, including rules.
            if body.get("solvedBy") != "OPENAI":
                raise AssertionError("Unexpected worker solvedBy contract")
            verify_pipeline(body.get("reasoning") or {})

    def validate_worker_logs(self, worker_log):
        executions = [line for line in worker_log.splitlines() if "Classification execution " in line]
        return len(executions) == self.sent and self.sent > 0 and all(
            "stage=PRE_AGENTIC_HIT resolved_by=NON_UNSPSC_RULE status_code=EXCLUDED" in line
            and "query_count=0 candidate_count=0 evaluation_decision=None" in line
            and "category_code=-1000 category_tier=SEGMENT" in line for line in executions
        ) and "ERROR:" not in worker_log


def pipeline_result():
    return {"stage": "PRE_AGENTIC_HIT", "final_result": dict(EXPECTED),
            "pre_agentic_result": {"lookup_hash": LOOKUP_HASH, "reasoning": {"matched_rule_label": "VAT"}},
            "identify_search_result": None, "retrieval_result": None, "evaluation_result": None}


class VerificationTests(unittest.TestCase):
    def test_stopping_a_user_does_not_interrupt_an_inflight_send(self):
        entered, release = Event(), Event()
        run = object.__new__(TaxExclusionRun)
        run.accepting, run.run_id, run.sent = True, "test", 0
        run.pending, run.queues = {}, {"input": "test-queue"}
        run.latencies, run.errors, run.failed = [], [], 0
        run.metric, run.sqs = Mock(), Mock()

        def delayed_send(**kwargs):
            entered.set()
            release.wait()

        run.sqs.send_message.side_effect = delayed_send
        user = gevent.spawn(run.publish)
        try:
            self.assertTrue(entered.wait(timeout=1))
            user.kill()
            release.set()
            gevent.sleep(0.01)
            self.assertEqual(run.sent, 1)
            self.assertEqual(len(run.pending), 1)
            self.assertEqual(run.sqs.send_message.call_count, 1)
            self.assertEqual(run.metric.call_count, 0)
            run.finish(next(iter(run.pending)))
            self.assertEqual(run.metric.call_count, 1)
            self.assertEqual(run.metric.call_args.args[0], "VAT / end-to-end")
        finally:
            release.set()
            user.kill()

    def test_expected_exclusion_and_both_event_contracts(self):
        result = pipeline_result()
        verify_pipeline(result)
        submitted = dict(FIXTURE, transactionId="tx", uploadedDocumentId="doc", correlationId="run:item")
        event = dict(submitted, eventType="LineItemProcessingCompleted", categoryCode="-1000",
                     categoryTier="SEGMENT", schemaVersion=1, solvedBy="OPENAI", reasoning=result)
        run = object.__new__(TaxExclusionRun)
        run.validate("result", event, submitted)
        run.validate("post", event, submitted)

    def test_wrong_exclusion_and_unexpected_agentic_execution_fail(self):
        for mutation in ("status", "agentic", "hash", "rule"):
            result = copy.deepcopy(pipeline_result())
            if mutation == "status":
                result["final_result"]["status_code"] = "SOLVED"
            elif mutation == "agentic":
                result["evaluation_result"] = {}
            elif mutation == "hash":
                result["pre_agentic_result"]["lookup_hash"] = "wrong"
            else:
                result["pre_agentic_result"]["reasoning"]["matched_rule_label"] = "Other rule"
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                verify_pipeline(result)

    def test_mismatched_transaction_and_failure_event_fail(self):
        submitted = dict(FIXTURE, transactionId="tx", uploadedDocumentId="doc", correlationId="run:item")
        event = dict(submitted, eventType="LineItemProcessingCompleted", categoryCode="-1000",
                     categoryTier="SEGMENT", schemaVersion=1)
        run = object.__new__(TaxExclusionRun)
        for key, value in (("transactionId", "wrong"), ("eventType", "LineItemProcessingFailed"),
                           ("categoryCode", "43211503"), ("uploadedDocumentId", None)):
            with self.subTest(key=key), self.assertRaises(AssertionError):
                run.validate("post", dict(event, **{key: value}), submitted)

    def test_nearest_rank_percentile_and_empty_run(self):
        self.assertIsNone(percentile([], 0.95))
        self.assertEqual(percentile(list(range(1, 101)), 0.95), 95)
        self.assertEqual(percentile([100, 10], 0.95), 100)


if __name__ == "__main__":
    unittest.main()
