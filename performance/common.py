"""Shared local worker/SQS lifecycle, event collection, and performance reporting."""
import json
import math
import os
import subprocess
import sys
import time
import tempfile
from textwrap import wrap
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4
from types import SimpleNamespace

import boto3
import gevent
from botocore.config import Config

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "13-lip-v2"


def percentile(values, fraction):
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)] if values else None


def evaluate_performance(latencies, elapsed, options):
    metrics = {"avg_ms": sum(latencies) / len(latencies) if latencies else None,
               "p95_ms": percentile(latencies, 0.95), "p99_ms": percentile(latencies, 0.99),
               "verified_per_second": len(latencies) / elapsed if elapsed > 0 else 0}
    checks = {f"{name}_within_limit": metrics[f"{name}_ms"] is not None
              and metrics[f"{name}_ms"] <= getattr(options, f"{name}_ms")
              for name in ("avg", "p95", "p99")}
    checks["throughput_meets_target"] = metrics["verified_per_second"] >= options.min_rps
    return metrics, checks


def failure_reason(report):
    reasons = list(report["errors"])
    if report["fatal"]:
        reasons.append(report["fatal"])
    thresholds = report.get("thresholds", {})
    for check, passed in report["checks"].items():
        if passed:
            continue
        if check in ("avg_within_limit", "p95_within_limit", "p99_within_limit"):
            metric = check.removesuffix("_within_limit")
            value = report[f"{metric}_ms"]
            reasons.append(f"{metric} {value:.2f} ms exceeds limit {thresholds.get(metric + '_ms')} ms"
                           if value is not None else f"{metric} unavailable: no verified completions")
        elif check == "throughput_meets_target":
            reasons.append(f"Throughput {report['verified_per_second']:.2f}/s below target {thresholds.get('min_rps')}/s")
        elif check == "minimum_samples":
            reasons.append(f"Only {report['sent']} messages; minimum {thresholds.get('min_samples')}")
        elif check in ("all_steps_verified", "no_failures"):
            if not reasons:
                reasons.append("Not all command steps completed successfully")
        else:
            reasons.append(check.replace("_", " "))
    return "; ".join(dict.fromkeys(str(reason) for reason in reasons)) or "Unspecified failure"


def display_results(rows):
    for scenario, result, reason in rows:
        print(f"{scenario}: {result}" + (f" — {reason}" if reason != "-" else ""), flush=True)


def display_failed_tests(rows):
    failed = [(scenario, reason) for scenario, result, reason in rows if result == "FAIL"]
    print(f"\nTest cases: {len(rows) - len(failed)} passed, {len(failed)} failed, {len(rows)} total", flush=True)
    if not failed:
        return
    print("\nFAILED TESTS", flush=True)
    border = "+" + "-" * 60 + "+" + "-" * 74 + "+"
    print(border, flush=True)
    print(f"| {'Test case':<58} | {'Reason for failure':<72} |", flush=True)
    print(border, flush=True)
    for scenario, reason in failed:
        title = scenario.replace("_", " ")
        titles = wrap(title, 58) or [""]
        reasons = wrap(" ".join(reason.split()), 72) or [""]
        for index in range(max(len(titles), len(reasons))):
            left = titles[index] if index < len(titles) else ""
            right = reasons[index] if index < len(reasons) else ""
            print(f"| {left:<58} | {right:<72} |", flush=True)
        print(border, flush=True)


def save_summary(scenario, passed, reason, report_path=None):
    path = os.getenv("PERF_RESULT_SUMMARY_FILE")
    if path:
        destination = Path(path)
        summary = json.loads(destination.read_text()) if destination.exists() else {}
        summary.update(scenario=scenario, passed=passed, reason=reason)
        if report_path is not None:
            summary["report_path"] = str(report_path)
        destination.write_text(json.dumps(summary))


def display_result(report, report_path):
    verdict = "PASSED" if report["passed"] else "FAILED"
    print(f"\nTEST {verdict}: {report['scenario']}", flush=True)
    reason = "-" if report["passed"] else failure_reason(report)
    display_results([(report["scenario"], "PASS" if report["passed"] else "FAIL", reason)])
    save_summary(report["scenario"], report["passed"], reason, report_path)
    rate = report["failure_rate_percent"]
    rate_text = f"{rate:.2f}%" if rate is not None else "unavailable (no executions)"
    print(f"Executions: {report['verified']} successful, {report['failed']} failed | Failure rate: {rate_text}", flush=True)
    timing = " | ".join(f"{name}: {report[name + '_ms']:.2f} ms" if report[name + '_ms'] is not None
                        else f"{name}: unavailable" for name in ("avg", "p95", "p99"))
    print(f"{timing} | Throughput: {report['verified_per_second']:.2f} workflows/second", flush=True)
    print(f"Report: {report_path}\n", flush=True)


def aggregate_reports(reports, latencies):
    successful = sum(report["verified"] for report in reports)
    failed = sum(report["failed"] for report in reports)
    sent = sum(report["sent"] for report in reports)
    duration = sum(report["total_seconds_including_drain"] for report in reports)
    if len(latencies) != successful:
        raise ValueError("Suite execution timings do not match successful execution counts")
    return {"sent": sent, "verified": successful, "failed": failed,
            "failure_rate_percent": failed / sent * 100 if sent else None,
            "avg_ms": sum(latencies) / successful if successful else None,
            "p95_ms": percentile(latencies, 0.95), "p99_ms": percentile(latencies, 0.99),
            "verified_per_second": successful / duration if duration > 0 else None,
            "total_seconds_including_drain": duration}


def display_suite_metrics(metrics):
    print("\nCOMBINED METRICS — ALL TESTS", flush=True)
    for label, key, unit in (("Average execution time", "avg_ms", "ms"),
                            ("P95 execution time", "p95_ms", "ms"),
                            ("P99 execution time", "p99_ms", "ms"),
                            ("Throughput", "verified_per_second", "workflows/s"),
                            ("Successful executions", "verified", ""),
                            ("Failed executions", "failed", ""),
                            ("Failure rate", "failure_rate_percent", "%")):
        value = metrics[key]
        text = "unavailable" if value is None else (
            str(value) if key in ("verified", "failed") else f"{value:.2f} {unit}")
        print(f"{label}: {text}", flush=True)


def run_all_scenarios(scenarios, arguments):
    """Run each scenario in its own Locust process, retaining CLI overrides."""
    outcomes = {}
    rows = []
    reports, groups, missing = [], {}, []
    suite_output = ROOT / "performance" / "results" / ("suite-" + uuid4().hex)
    suite_output.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="locust-summary-") as directory:
        for scenario in scenarios:
            print(f"\nRUNNING TEST: {scenario}", flush=True)
            summary_path = Path(directory) / f"{scenario}.json"
            env = dict(os.environ, PERF_RESULT_SUMMARY_FILE=str(summary_path))
            command = [sys.executable, "-m", "locust", *arguments, "--scenario", scenario]
            code = outcomes[scenario] = subprocess.run(command, cwd=ROOT, env=env).returncode
            summary = json.loads(summary_path.read_text()) if summary_path.exists() else None
            reason = "-" if code == 0 else (
                summary["reason"] if summary and not summary["passed"]
                else f"Process exited with code {code}; inspect terminal output")
            rows.append((scenario, "PASS" if code == 0 else "FAIL", reason))
            if summary and summary.get("report_path"):
                report_path = Path(summary["report_path"])
                report = json.loads(report_path.read_text())
                timings = json.loads((report_path.parent / "execution_timings.json").read_text())
                reports.append(report)
                group = groups.setdefault(report["measurement"], {"reports": [], "latencies": []})
                group["reports"].append(report)
                group["latencies"].extend(timings)
            else:
                missing.append(scenario)
    print("\nALL TESTS RESULTS", flush=True)
    display_results(rows)
    metrics = {}
    for measurement, group in groups.items():
        print(f"\nMeasurement: {measurement}", flush=True)
        metrics[measurement] = aggregate_reports(group["reports"], group["latencies"])
        display_suite_metrics(metrics[measurement])
    if missing:
        print(f"Metrics unavailable for: {', '.join(missing)}", flush=True)
    passed = bool(outcomes) and all(code == 0 for code in outcomes.values()) and not missing
    suite_report = {"passed": passed, "metrics_complete": not missing, "missing_reports": missing,
                    "failed_tests": [{"scenario": scenario, "reason": reason}
                                     for scenario, result, reason in rows if result == "FAIL"],
                    "execution_metrics": metrics, "scenario_exit_codes": outcomes,
                    "scenario_reports": reports, "command_arguments": arguments,
                    "aggregation": "Timings pooled separately by measurement type. CLI timings include process startup; "
                                   "worker timings measure submission until both output events. Individual failures fail the suite."}
    suite_path = suite_output / "report.json"
    suite_path.write_text(json.dumps(suite_report, indent=2))
    print(f"Combined report: {suite_path}", flush=True)
    display_failed_tests(rows)
    print(f"ALL TESTS {'PASSED' if passed else 'FAILED'}", flush=True)
    return 0 if passed else 1


class WorkerScenario:
    """Subclass supplies request data, setup, outcome checks, and stage-log checks."""

    input_payload = None
    run_prefix = "scenario"
    metric_name = "Scenario"
    database_check_name = "database_postconditions"

    def prepare(self, output):
        raise NotImplementedError

    def verify_after(self):
        raise NotImplementedError

    def validate_worker_logs(self, worker_log):
        raise NotImplementedError

    def __init__(self, environment):
        self.environment = environment
        self.options = SimpleNamespace(**{
            name: getattr(environment.parsed_options, name)
            for name in ("timeout", "interval", "avg_ms", "p95_ms", "p99_ms", "min_rps", "min_samples")
        })
        self.run_id = self.run_prefix + "-" + uuid4().hex
        self.output = ROOT / "performance" / "results" / self.run_id
        self.output.mkdir(parents=True)
        self.queues = {}
        self.pending = {}
        self.latencies = []
        self.sent = 0
        self.failed = 0
        self.duplicates = 0
        self.errors = []
        self.worker = None
        self.collector = None
        self.logs = []
        self.started = None
        self.fatal = None
        self.accepting = False

    def start(self):
        endpoint = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
        host = urlparse(endpoint).hostname or ""
        if host not in ("localhost", "127.0.0.1") and not host.endswith(".localhost.localstack.cloud"):
            raise ValueError("This scenario requires a local LocalStack AWS_ENDPOINT_URL")
        if self.options.timeout <= 0 or self.options.interval <= 0:
            raise ValueError("Timeout and publishing interval must be positive")
        if any(getattr(self.options, name) <= 0 for name in ("avg_ms", "p95_ms", "p99_ms")) or self.options.min_rps < 0 or self.options.min_samples < 1:
            raise ValueError("Invalid performance thresholds")
        self.prepare(self.output)
        self.sqs = boto3.client(
            "sqs", endpoint_url=endpoint, region_name=os.getenv("AWS_REGION", "eu-west-2"),
            aws_access_key_id="test", aws_secret_access_key="test",
            config=Config(connect_timeout=3, read_timeout=5, retries={"max_attempts": 1}),
        )
        for kind in ("input", "result", "post"):
            self.queues[kind] = self.sqs.create_queue(QueueName=f"{self.run_id}-{kind}")["QueueUrl"]
        env = dict(os.environ, AWS_ENDPOINT_URL=endpoint, AWS_ACCESS_KEY_ID="test", AWS_SECRET_ACCESS_KEY="test",
                   AWS_REGION=os.getenv("AWS_REGION", "eu-west-2"), DB_SCHEMA_SYNC="false",
                   SEED_NON_UNSPSC_RULES="false", SEED_STABLE_LOOKUPS="false", SEED_UNSTABLE_LOOKUPS="false",
                   LINE_ITEM_INPUT_QUEUE_URL=self.queues["input"], LINE_ITEM_RESULT_QUEUE_URL=self.queues["result"],
                   DOCUMENT_METADATA_SQS_URL=self.queues["result"], OCR_STATUS_QUEUE_URL=self.queues["result"],
                   POST_OCR_QUEUE_URL=self.queues["post"], WORKER_ENABLED="true", SQS_WAIT_TIME_SECONDS="1",
                   LOG_LEVEL="INFO")
        self.logs = [(self.output / name).open("w") for name in ("worker.stdout.log", "worker.stderr.log")]
        self.worker = subprocess.Popen([sys.executable, "-u", "main.py"], cwd=APP, env=env,
                                       stdout=self.logs[0], stderr=self.logs[1])
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self.worker.poll() is not None:
                raise RuntimeError("Worker exited during startup; inspect worker.stderr.log")
            if "Starting 13-lip-v2 worker loop" in (self.output / "worker.stderr.log").read_text():
                break
            gevent.sleep(0.1)
        else:
            raise TimeoutError("Worker did not become ready within 15 seconds")
        self.evidence = (self.output / "events.jsonl").open("w")
        self.started = time.monotonic()
        self.accepting = True
        self.collector = gevent.spawn(self.collect)

    def metric(self, name, elapsed, error=None):
        self.environment.events.request.fire(request_type="SQS", name=name,
            response_time=elapsed, response_length=0, exception=error, context={"run_id": self.run_id})

    def publish(self):
        # Locust stops user greenlets at the time limit. Let an already-started
        # send finish independently so drain accounting includes its outcome.
        gevent.spawn(self._publish).join()

    def _publish(self):
        if not self.accepting:
            return
        correlation = f"{self.run_id}:{uuid4()}"
        body = dict(self.input_payload, schemaVersion=1, eventType="LineItemProcessingRequested", eventId=str(uuid4()),
                    occurredAt=datetime.now(timezone.utc).isoformat(), transactionId=str(uuid4()),
                    uploadedDocumentId=str(uuid4()), correlationId=correlation)
        started = time.monotonic()
        self.pending[correlation] = {"started": started, "body": body, "received": set()}
        self.sent += 1
        try:
            self.sqs.send_message(QueueUrl=self.queues["input"], MessageBody=json.dumps(body))
        except Exception as exc:
            self.finish(correlation, exc)

    def validate(self, kind, body, expected):
        for key in ("orgId", "transactionId", "uploadedDocumentId", "lineItemIndex", "lineItemText", "correlationId"):
            if body.get(key) != expected[key]:
                raise AssertionError(f"{kind}: incorrect {key}")
        for key, value in {"eventType": "LineItemProcessingCompleted", "schemaVersion": 1}.items():
            if body.get(key) != value:
                raise AssertionError(f"{kind}: expected {key}={value!r}, received {body.get(key)!r}")

    def finish(self, correlation, error=None):
        item = self.pending.pop(correlation, None)
        if item is None:
            return
        elapsed = (time.monotonic() - item["started"]) * 1000
        if error:
            self.failed += 1
            self.errors.append(str(error))
        else:
            self.latencies.append(elapsed)
        self.metric(f"{self.metric_name} / end-to-end", elapsed, error)

    def collect(self):
        try:
            while True:
                if self.worker.poll() is not None:
                    raise RuntimeError("Worker exited during the test")
                for kind in ("result", "post"):
                    response = self.sqs.receive_message(QueueUrl=self.queues[kind], MaxNumberOfMessages=10,
                                                       WaitTimeSeconds=0, VisibilityTimeout=10)
                    for message in response.get("Messages", []):
                        body = json.loads(message["Body"])
                        correlation = body.get("correlationId")
                        item = self.pending.get(correlation)
                        self.evidence.write(json.dumps({"queue": kind, "observed_at": datetime.now(timezone.utc).isoformat(),
                                                        "event": body}) + "\n")
                        self.evidence.flush()
                        if item is None:
                            self.duplicates += 1
                            self.errors.append("Duplicate or unknown correlation on isolated queue")
                        else:
                            try:
                                self.validate(kind, body, item["body"])
                                if kind in item["received"]:
                                    self.duplicates += 1
                                    raise AssertionError(f"Duplicate {kind} event")
                                item["received"].add(kind)
                                if item["received"] == {"result", "post"}:
                                    self.finish(correlation)
                            except Exception as exc:
                                self.finish(correlation, exc)
                        self.sqs.delete_message(QueueUrl=self.queues[kind], ReceiptHandle=message["ReceiptHandle"])
                now = time.monotonic()
                for correlation, item in list(self.pending.items()):
                    if now - item["started"] >= self.options.timeout:
                        self.finish(correlation, TimeoutError("Timed out waiting for both worker output events"))
                gevent.sleep(0.02)
        except Exception as exc:
            self.fatal = str(exc)
            self.accepting = False

    def stop(self):
        self.accepting = False
        load_seconds = time.monotonic() - self.started if self.started else 0
        deadline = time.monotonic() + self.options.timeout
        while self.pending and not self.fatal and time.monotonic() < deadline:
            gevent.sleep(0.05)
        for correlation in list(self.pending):
            self.finish(correlation, TimeoutError(self.fatal or "Completion deadline exceeded"))
        # Both outputs precede the input delete; allow that final acknowledgement.
        backlog = None
        if self.started and not self.fatal:
            while time.monotonic() < deadline:
                attrs = self.sqs.get_queue_attributes(QueueUrl=self.queues["input"], AttributeNames=[
                    "ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible"])["Attributes"]
                backlog = sum(int(v) for v in attrs.values())
                if backlog == 0:
                    break
                gevent.sleep(0.1)
        elapsed = time.monotonic() - self.started if self.started else 0
        try:
            after = self.verify_after()
        except Exception as exc:
            after = {"error": str(exc)}
            self.errors.append(str(exc))
        metrics, performance_checks = evaluate_performance(self.latencies, elapsed, self.options)
        worker_log_path = self.output / "worker.stderr.log"
        worker_log = worker_log_path.read_text() if worker_log_path.exists() else ""
        stage_logs_ok = self.validate_worker_logs(worker_log)
        checks = {
            "setup_and_collector": self.started is not None and not self.fatal,
            "minimum_samples": self.sent >= self.options.min_samples,
            "all_submitted_verified": len(self.latencies) == self.sent and self.failed == 0,
            "no_duplicate_events": self.duplicates == 0,
            self.database_check_name: "error" not in after,
            "input_queue_drained": backlog == 0,
            "worker_stage_logs_match": stage_logs_ok,
            **performance_checks,
        }
        report = {"run_id": self.run_id, "scenario": self.environment.parsed_options.scenario,
                  "passed": all(checks.values()), "checks": checks,
                  "sent": self.sent, "verified": len(self.latencies), "failed": self.failed,
                  "failure_rate_percent": self.failed / self.sent * 100 if self.sent else None,
                  "duplicate_events": self.duplicates, "load_seconds": load_seconds,
                  "drain_seconds": elapsed - load_seconds,
                  "total_seconds_including_drain": elapsed, **metrics,
                  "input_backlog": backlog,
                  "thresholds": {"avg_ms": self.options.avg_ms, "p95_ms": self.options.p95_ms,
                                 "p99_ms": self.options.p99_ms, "min_rps": self.options.min_rps,
                                 "min_samples": self.options.min_samples},
                  "database_after": after, "errors": self.errors, "fatal": self.fatal,
                  "worker_count": 1, "measurement": "submission until both result and post-OCR events observed"}
        (self.output / "execution_timings.json").write_text(json.dumps(self.latencies))
        (self.output / "report.json").write_text(json.dumps(report, indent=2))
        self.environment.process_exit_code = 0 if report["passed"] else 1
        display_result(report, self.output / "report.json")
        return report

    def cleanup(self):
        if self.collector:
            self.collector.kill()
        if self.worker and self.worker.poll() is None:
            self.worker.terminate()
            try:
                self.worker.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.worker.kill()
                self.worker.wait()
        for stream in self.logs:
            stream.close()
        if hasattr(self, "evidence"):
            self.evidence.close()
        # Only the queues created by this run are removed.
        for url in self.queues.values():
            self.sqs.delete_queue(QueueUrl=url)

