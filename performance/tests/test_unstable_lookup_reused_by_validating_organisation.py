"""Organisation 111… reuses its own approved unstable cleaning-service lookup."""
import copy
import unittest

from performance.common import WorkerScenario
from performance.setup.unstable_lookup_reused_by_validating_organisation import (
    EXPECTED, FIXTURE, FIXTURE_ID, LOOKUP_HASH, prepare, restore, verify, verify_pipeline,
)


class UnstableLookupRun(WorkerScenario):
    fixture = FIXTURE
    run_prefix = "unstable-validating"
    metric_name = "Unstable validating lookup"
    database_check_name = "unstable_fixture_unchanged"

    def prepare(self, output):
        self.baseline = prepare(output)["after_cli"]

    def verify_after(self):
        after = verify()
        if after != self.baseline:
            raise AssertionError("Unstable fixture changed during load, including solved_for or timestamps")
        return after

    def validate(self, kind, body, expected):
        super().validate(kind, body, expected)
        for key, value in {"categoryCode": "76111501", "categoryTier": "COMMODITY"}.items():
            if body.get(key) != value:
                raise AssertionError(f"{kind}: expected {key}={value!r}")
        if kind == "result":
            if body.get("solvedBy") != "OPENAI" or body.get("categoryTitle") != "Building cleaning services":
                raise AssertionError("Incorrect completed event outcome")
            verify_pipeline(body.get("reasoning") or {}, self.baseline["fixture_id"])

    def cleanup(self):
        try:
            super().cleanup()
        finally:
            restore(self.output)

    def validate_worker_logs(self, worker_log):
        executions = [line for line in worker_log.splitlines() if "Classification execution " in line]
        return len(executions) == self.sent and self.sent > 0 and all(
            "stage=PRE_AGENTIC_HIT resolved_by=UNSTABLE_LOOKUP status_code=SOLVED" in line
            and "query_count=0 candidate_count=0 evaluation_decision=None" in line
            and "category_code=76111501 category_tier=COMMODITY" in line for line in executions
        ) and "ERROR:" not in worker_log


class VerificationTests(unittest.TestCase):
    def result(self):
        return {"stage": "PRE_AGENTIC_HIT", "final_result": dict(EXPECTED),
                "pre_agentic_result": dict(EXPECTED, lookup_hash=LOOKUP_HASH,
                    reasoning={"matched_row_id": FIXTURE_ID, "stable": False}),
                "identify_search_result": None, "retrieval_result": None, "evaluation_result": None}

    def test_exact_unstable_fixture_and_both_output_events(self):
        result = self.result()
        verify_pipeline(result)
        submitted = dict(FIXTURE, transactionId="tx", uploadedDocumentId="doc", correlationId="run:item")
        body = dict(submitted, schemaVersion=1, eventType="LineItemProcessingCompleted", solvedBy="OPENAI",
                    categoryCode="76111501", categoryTier="COMMODITY", categoryTitle="Building cleaning services", reasoning=result)
        run = object.__new__(UnstableLookupRun)
        run.baseline = {"fixture_id": FIXTURE_ID}
        for kind in ("result", "post"):
            run.validate(kind, body, submitted)

    def test_stable_wrong_fixture_and_agentic_results_are_rejected(self):
        for mutation in ("stable", "fixture", "agentic", "code"):
            result = copy.deepcopy(self.result())
            if mutation == "stable":
                result["final_result"]["resolved_by"] = "STABLE_LOOKUP"
            elif mutation == "fixture":
                result["pre_agentic_result"]["reasoning"]["matched_row_id"] = "wrong"
            elif mutation == "agentic":
                result["identify_search_result"] = {}
            else:
                result["final_result"]["unspsc_code"] = "43211503"
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                verify_pipeline(result)


if __name__ == "__main__":
    unittest.main()
