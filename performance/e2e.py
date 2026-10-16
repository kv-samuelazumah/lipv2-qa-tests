"""Live E2E checks shared by the workbook scenarios; no response substitution."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import gevent

from performance.common import APP, WorkerScenario, display_result, percentile

from performance.data_setup import (
    ORG1, ORG2, ORG3, ORG4, database_state, payload_hash as lookup_hash,
)

STAGES = ("identify_search_result", "retrieval_result", "evaluation_result")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def reusable(row, payload):
    return row is not None and (row["stable"] or payload.get("orgId") in row["solved_for"])


def no_agentic(result):
    for stage in STAGES:
        require(stage in result and result[stage] is None, f"{stage} must be null")


def rule_result(result, payload, rule):
    require(result.get("stage") == "PRE_AGENTIC_HIT", "Expected PRE_AGENTIC_HIT")
    expected = dict(resolved_by="NON_UNSPSC_RULE", status_code=rule["status"],
                    policy_code=rule["policy"], unspsc_code=rule["code"],
                    unspsc_level=rule["level"], selected_label=rule["label"], lookup_hash=lookup_hash(payload))
    for name in ("pre_agentic_result", "final_result"):
        actual = result.get(name) or {}
        for key, value in expected.items():
            require(actual.get(key) == value, f"{name}.{key}: expected {value!r}, got {actual.get(key)!r}")
    reasoning = result["pre_agentic_result"].get("reasoning") or {}
    require(reasoning.get("rule_order") == rule["order"], "Wrong rule order")
    require(reasoning.get("matched_rule_label") == rule["label"], "Wrong rule label")
    require(reasoning.get("matched_rule_id") == rule["id"], "Wrong rule ID")
    no_agentic(result)


def lookup_result(result, payload, row):
    require(reusable(row, payload), "Prerequisite: an existing reusable classification is required")
    require(result.get("stage") == "PRE_AGENTIC_HIT", "Expected lookup hit")
    expected = dict(resolved_by="STABLE_LOOKUP" if row["stable"] else "UNSTABLE_LOOKUP",
                    status_code=row["status"], policy_code=row["policy"], unspsc_code=row["code"],
                    unspsc_level=row["level"], lookup_hash=row["lookup_hash"], selected_label=row["label"])
    for name in ("pre_agentic_result", "final_result"):
        for key, value in expected.items():
            require((result.get(name) or {}).get(key) == value, f"{name}.{key} differs from saved row")
    reasoning = result["pre_agentic_result"].get("reasoning") or {}
    require(reasoning.get("matched_row_id") == row["id"], "Wrong saved row reused")
    require(reasoning.get("stable") == row["stable"], "Wrong stability flag")
    no_agentic(result)


def supported_classification(final, retrieval):
    candidates = retrieval.get("candidates") or []
    supported = {(str(c.get("code")), str(c.get("level", "")).upper()) for c in candidates}
    for candidate in candidates:
        for level, node in (candidate.get("hierarchy_path") or {}).items():
            if node:
                supported.add((str(node.get("code")), level.upper()))
    require((final["unspsc_code"], final["unspsc_level"].upper()) in supported,
            "Selected classification is not supported by retrieved candidates or their hierarchy")


def agentic_result(result, payload, before, code=None, unresolved=False, service=False):
    require(result.get("pre_agentic_result") is None, "Saved answer or rule unexpectedly applied")
    for stage in STAGES[:2]:
        require(isinstance(result.get(stage), dict), f"{stage} did not run")
    retrieval = result["retrieval_result"]
    if retrieval.get("candidates"):
        require(isinstance(result.get("evaluation_result"), dict), "Evaluation did not run")
    final = result.get("final_result") or {}
    after = database_state(payload)["row"]
    if unresolved or final.get("status_code") == "UNRESOLVED":
        require(code is None, "Expected a successful commodity classification")
        require(result.get("stage") == "UNABLE_TO_RESOLVE", "Expected UNABLE_TO_RESOLVE")
        require(final.get("status_code") == "UNRESOLVED", "Expected UNRESOLVED")
        require(all(final.get(k) is None for k in ("unspsc_code", "unspsc_level", "policy_code")),
                "Unresolved input must have no code, level or policy")
        require(after == before, "Unresolved input changed its saved classification")
        return
    require(result.get("stage") == "MATCH_OBTAINED" and final.get("status_code") == "SOLVED",
            "Expected a successful live classification or justified UNRESOLVED")
    require(final.get("policy_code") is None, "Unexpected exclusion policy")
    require(final.get("unspsc_code") and final.get("unspsc_level"), "Missing classification")
    if code:
        require(final["unspsc_code"] == code and final["unspsc_level"] == "COMMODITY", "Wrong commodity")
    supported_classification(final, retrieval)
    if service:
        hypothesis = result["identify_search_result"].get("item_hypothesis") or {}
        require(hypothesis.get("item_nature") == "service", "Expected a service identity")
    require(after is not None and after["code"] == final["unspsc_code"] and after["status"] == "SOLVED",
            "Successful classification was not saved")
    require(payload["orgId"] in after["solved_for"], "Organisation agreement was not saved")
    require(final.get("lookup_hash") == lookup_hash(payload), "Wrong saved lookup hash")


class LiveCase:
    def __init__(self, spec, fixture):
        self.spec = spec
        self.inputs = [json.loads(line) for line in Path(fixture).read_text().splitlines() if line.strip()]

    def rule_precondition(self, payload):
        state = database_state(payload)
        require(not reusable(state["row"], payload), "Prerequisite: a reusable saved classification already exists")
        rule = state["rule"]
        require(rule is not None, "Prerequisite: the exclusion rule must be enabled")
        for key, value in self.spec["rule"].items():
            require(rule.get(key) == value, f"Prerequisite: rule {key} must be {value!r}")
        return state

    def execute(self, payload, output, index, timeout, invalid=False):
        raw = payload if isinstance(payload, str) else json.dumps(payload)
        command = [sys.executable, "main.py", "--input-json", raw, "--run-until-stage", "full"]
        env = dict(os.environ, DB_SCHEMA_SYNC="false", SEED_NON_UNSPSC_RULES="false",
                   SEED_STABLE_LOOKUPS="false", SEED_UNSTABLE_LOOKUPS="false")
        started = time.monotonic()
        completed = subprocess.run(command, cwd=APP, env=env, capture_output=True, text=True, timeout=timeout)
        (output / f"{index:02d}.stdout.log").write_text(completed.stdout)
        (output / f"{index:02d}.stderr.log").write_text(completed.stderr)
        require(completed.returncode != 0 if invalid else completed.returncode == 0,
                f"Unexpected CLI exit code {completed.returncode}; inspect {index:02d}.stderr.log")
        if invalid:
            require("ValueError" in completed.stderr or "JSONDecodeError" in completed.stderr,
                    "Input was not rejected by validation/parsing")
            require("Classification execution " not in completed.stderr, "Invalid input entered classification")
            return None, (time.monotonic() - started) * 1000
        response = json.loads(completed.stdout.strip().splitlines()[-1])
        require("ERROR:" not in completed.stderr, "CLI logged an application error")
        require(isinstance(response, (dict, list)), "CLI returned no structured response")
        if isinstance(payload, dict):
            require(response.get("input") == dict(org_id=payload["orgId"], supplier_raw=payload["supplier"],
                                                  line_item_raw=payload["lineItemText"]), "CLI input differs")
            require(response.get("cli", {}).get("run_until_stage") == "full", "Full processing was not run")
        return response, (time.monotonic() - started) * 1000

    def is_lookup_step(self, step):
        mode = self.spec["mode"]
        return (
            mode == "lookup"
            or (mode == "repeat" and step > 0)
            or (mode == "promotion" and step == 3)
            or (mode == "change" and step == 1)
        )

    def precondition(self, payload, step):
        mode = self.spec["mode"]
        if mode == "invalid":
            return None
        if mode == "batch":
            return self.batch_precondition(payload)

        state = database_state(payload)
        row = state["row"]
        if self.is_lookup_step(step):
            self.lookup_precondition(payload, state)
        elif mode == "isolation" or (mode == "change" and step == 0):
            self.private_precondition(payload, state)
        elif mode in ("promotion", "change") and step > 0:
            require(not reusable(row, payload), "Organisation must independently classify this item")
            require(state["rule"] is None, "Unexpected exclusion rule")
        else:
            require(row is None, "Prerequisite: this fresh classification case requires no saved row")
            require(state["rule"] is None, "Prerequisite: no exclusion rule may match")
        return state

    def batch_precondition(self, payload):
        states = [database_state(item) for item in payload]
        require(states[0]["rule"] and states[0]["rule"]["label"] == "PAYE", "PAYE rule is required")
        require(not reusable(states[0]["row"], payload[0]), "PAYE lookup masks the rule")
        row = states[2]["row"]
        require(row and row["stable"] and row["status"] == "SOLVED" and row["label"] == "Ball point pens",
                "Prerequisite: shared pen classification is required")
        require(states[3]["row"] is None and states[3]["rule"] is None,
                "Prerequisite: pump input must have no saved answer or matching rule")
        return states

    def lookup_precondition(self, payload, state):
        row = state["row"]
        require(reusable(row, payload), "Prerequisite: existing reusable classification is required")
        expected_code = self.spec.get("code")
        require(row["status"] == "SOLVED" and (not expected_code or
                row["code"] == expected_code and row["level"] == "COMMODITY"),
                "Prerequisite: saved classification has wrong code, level or status")
        if self.spec.get("new_org"):
            require(payload["orgId"] not in row["solved_for"], "New organisation is already in agreement list")
        if self.spec.get("stable") is not None:
            require(row["stable"] == self.spec["stable"], "Prerequisite: wrong stability")
        if self.spec.get("solved_for"):
            require(set(row["solved_for"]) == set(self.spec["solved_for"]), "Prerequisite: wrong agreement list")
        if self.spec.get("conflicting_rule"):
            require(state["rule"] and state["rule"]["status"] == "EXCLUDED"
                    and state["rule"]["code"] == "-1000", "Prerequisite: conflicting exclusion rule is required")

    def private_precondition(self, payload, state):
        row = state["row"]
        orgs = self.spec["old_orgs"]
        require(row and not row["stable"] and set(row["solved_for"]) == set(orgs)
                and len(row["solved_for"]) == len(orgs) and row["code"] == self.spec["old_code"]
                and row["level"] == "COMMODITY" and row["status"] == "SOLVED",
                "Prerequisite: original private classification differs")
        require(not reusable(row, payload) and state["rule"] is None,
                "Request must enter independent classification")

    def validate(self, payload, response, before, step):
        mode = self.spec["mode"]
        if mode == "invalid":
            return
        if mode == "batch":
            self.validate_batch(payload, response, before)
            return

        result = response.get("result") or {}
        row = before["row"]
        if self.is_lookup_step(step):
            lookup_result(result, payload, row)
            require(database_state(payload)["row"] == row, "Lookup changed its saved row")
            self.validate_label(result["final_result"])
            return

        self.validate_agentic(payload, result, row, step)

    def validate_batch(self, payload, response, before):
        require(isinstance(response, list) and len(response) == 4, "Batch must return four ordered results")
        for item, supplied in zip(response, payload):
            require(item.get("input", {}).get("supplier_raw") == supplied["supplier"], "Batch order changed")
        rule_result(response[0]["result"], payload[0], before[0]["rule"])
        require(response[1].get("result") is None and response[1].get("error", {}).get("type") == "ValueError",
                "Missing-description item was not rejected")
        require(database_state(payload[1])["row"] == before[1]["row"], "Invalid batch item changed database")
        lookup_result(response[2]["result"], payload[2], before[2]["row"])
        require(database_state(payload[2])["row"] == before[2]["row"], "Pen lookup changed")
        pump = response[3]["result"]
        agentic_result(pump, payload[3], before[3]["row"])
        final = pump["final_result"]
        if final["status_code"] == "SOLVED":
            require(final.get("unspsc_code") == self.spec["pump_code"]
                    and final.get("unspsc_level") == self.spec["pump_level"],
                    "Expected the broad Pump parts and accessories classification")

    def validate_label(self, final):
        if self.spec.get("label") and final.get("status_code") == "SOLVED":
            require(final.get("selected_label") == self.spec["label"], "Wrong classification label")

    def validate_agentic(self, payload, result, row, step):
        mode = self.spec["mode"]
        independent = mode == "isolation" or (mode == "change" and step == 2)
        code = None if independent else self.spec.get("code")
        agentic_result(result, payload, row, code=code,
                       unresolved=self.spec.get("unresolved", False), service=self.spec.get("service", False))
        final = result.get("final_result") or {}
        after = database_state(payload)["row"]
        if self.spec.get("identity_terms"):
            hypothesis = result["identify_search_result"].get("item_hypothesis") or {}
            identity = hypothesis.get("primary_identity", "").lower()
            require(any(term in identity for term in self.spec["identity_terms"]),
                    "Identify did not recognise the purchased item")
        self.validate_label(final)
        if mode == "isolation" and final.get("status_code") == "SOLVED":
            self.validate_isolation(payload, row, after)
        if mode in ("promotion", "repeat", "change") or self.spec.get("fresh"):
            self.validate_agreements(payload, row, after, final, step)

    def validate_isolation(self, payload, row, after):
        orgs = [*row["solved_for"], payload["orgId"]] if after["code"] == row["code"] else [payload["orgId"]]
        require(after["id"] == row["id"] and set(after["solved_for"]) == set(orgs)
                and len(after["solved_for"]) == len(orgs) and not after["stable"], "Wrong isolation persistence")

    def validate_agreements(self, payload, row, after, final, step):
        mode = self.spec["mode"]
        if mode == "promotion":
            orgs = [ORG1, ORG2, ORG3][:step + 1]
        elif mode == "change" and step == 2:
            if final.get("status_code") == "UNRESOLVED":
                return
            orgs = [ORG4, ORG1] if after["code"] == row["code"] else [ORG1]
        else:
            orgs = [payload["orgId"]]
        require(after and set(after["solved_for"]) == set(orgs) and len(after["solved_for"]) == len(orgs),
                "Agreement list contains missing or duplicate organisations")
        require(after["stable"] == (len(orgs) >= 3), "Wrong shared/private state")
        if row:
            require(after["id"] == row["id"], "Existing classification row was replaced")


class RuleScenario(WorkerScenario):
    """Load-test rule cases through the real SQS worker."""
    case = None

    def __init__(self, environment):
        payload = self.case.inputs[0]
        self.input_payload = dict(orgId=payload["orgId"], supplierRaw=payload["supplier"],
                                  lineItemText=payload["lineItemText"], lineItemIndex=0)
        self.metric_name = self.case.spec["title"]
        self.run_prefix = self.case.spec["index"]
        super().__init__(environment)

    def prepare(self, output):
        self.baseline = self.case.rule_precondition(self.case.inputs[0])
        response, _ = self.case.execute(self.case.inputs[0], output, 0, self.options.timeout)
        rule_result(response["result"], self.case.inputs[0], self.baseline["rule"])
        self.verify_after()
        (output / "setup.json").write_text(json.dumps(self.baseline, indent=2))

    def verify_after(self):
        require(hasattr(self, "baseline"), self.fatal or "Rule scenario setup did not complete")
        state = self.case.rule_precondition(self.case.inputs[0])
        require(state == self.baseline, "Rule processing changed its database prerequisites")
        return state

    def validate(self, kind, body, expected):
        super().validate(kind, body, expected)
        rule = self.baseline["rule"]
        for key, value in dict(categoryCode=rule["code"], categoryTier=rule["level"]).items():
            require(body.get(key) == value, f"{kind}: wrong {key}")
        if kind == "result":
            # The worker labels all coded outcomes OPENAI, including rule matches.
            require(body.get("solvedBy") == "OPENAI", "Unexpected worker solvedBy contract")
            rule_result(body.get("reasoning") or {}, self.case.inputs[0], rule)
            require(body.get("categoryTitle") == rule["label"], "Wrong event label")

    def validate_worker_logs(self, worker_log):
        rule = self.baseline["rule"] if hasattr(self, "baseline") else self.case.spec["rule"]
        executions = [line for line in worker_log.splitlines() if "Classification execution " in line]
        return self.sent > 0 and len(executions) == self.sent and "ERROR:" not in worker_log and all(
            f"stage=PRE_AGENTIC_HIT resolved_by=NON_UNSPSC_RULE status_code={rule['status']}" in line
            and "query_count=0 candidate_count=0 evaluation_decision=None" in line
            and f"category_code={rule['code']} category_tier={rule['level']}" in line for line in executions)


class CliScenario(WorkerScenario):
    """Run stateful/grouped CLI cases once, in order, without replaying first-use requests."""
    case = None

    def start(self):
        self.started = time.monotonic()
        self.accepting = True
        self.finished = False
        self.metric_name = self.case.spec["title"]

    def publish(self):
        if self.accepting:
            self.accepting = False
            self.collector = gevent.spawn(self.run_commands)

    def run_commands(self):
        try:
            for index, payload in enumerate(self.case.inputs):
                before = self.case.precondition(payload, index)
                (self.output / f"{index:02d}.before.json").write_text(json.dumps(before, indent=2))
                self.sent += 1
                try:
                    self.run_input(payload, before, index)
                except Exception as exc:
                    self.failed += 1
                    self.errors.append(f"Input {index + 1}: {exc}")
                    self.metric(f"{self.metric_name} / CLI", 0, exc)
                    if not self.case.spec.get("continue_on_failure", False):
                        raise
            self.finished = True
        except Exception as exc:
            self.fatal = str(exc)
        finally:
            gevent.spawn(self.environment.runner.quit)

    def run_input(self, payload, before, index):
        invalid = self.case.spec["mode"] == "invalid"
        protected = payload if isinstance(payload, dict) else dict(
            supplier="Workplace Safety Supplies", lineItemText="Safety helmet")
        original = database_state(protected)["row"] if invalid else None
        response, elapsed = self.case.execute(payload, self.output, index, self.options.timeout, invalid)
        self.case.validate(payload, response, before, index)
        if invalid:
            require(database_state(protected)["row"] == original, "Invalid input changed its database row")
        self.latencies.append(elapsed)
        self.metric(f"{self.metric_name} / CLI", elapsed)

    def stop(self):
        elapsed = time.monotonic() - self.started if self.started else 0
        checks = {"all_steps_verified": getattr(self, "finished", False) and len(self.latencies) == len(self.case.inputs),
                  "no_failures": not self.fatal and self.failed == 0}
        timings = self.latencies
        report = dict(scenario=self.environment.parsed_options.scenario, passed=all(checks.values()), checks=checks,
                      sent=self.sent, verified=len(timings), failed=self.failed, errors=self.errors, fatal=self.fatal,
                      avg_ms=sum(timings) / len(timings) if timings else None,
                      p95_ms=percentile(timings, .95), p99_ms=percentile(timings, .99),
                      verified_per_second=len(timings) / elapsed if elapsed else 0,
                      failure_rate_percent=self.failed / self.sent * 100 if self.sent else None,
                      total_seconds_including_drain=elapsed, measurement="CLI process including startup; functional checks only",
                      expected=self.case.spec["expected"], preconditions=self.case.spec["preconditions"])
        (self.output / "execution_timings.json").write_text(json.dumps(timings))
        path = self.output / "report.json"
        path.write_text(json.dumps(report, indent=2))
        self.environment.process_exit_code = 0 if report["passed"] else 1
        display_result(report, path)
        return report

    def cleanup(self):
        if self.collector and not self.collector.ready():
            self.collector.kill()
