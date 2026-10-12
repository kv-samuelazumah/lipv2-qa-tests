from locust import User, events, task
from locust.runners import LocalRunner

import sys
import importlib
import gevent
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / "13-lip-v2" / ".env")

from performance.common import WorkerScenario, run_all_scenarios, save_summary


def discover_scenarios():
    scenarios = {}
    for path in sorted((ROOT / "performance" / "tests").glob("test_*.py")):
        module = importlib.import_module(f"performance.tests.{path.stem}")
        classes = [value for value in vars(module).values()
                   if isinstance(value, type) and issubclass(value, WorkerScenario)
                   and value is not WorkerScenario and value.__module__ == module.__name__]
        if len(classes) > 1:
            raise ValueError(f"Define only one WorkerScenario subclass in {path.name}")
        if classes:
            scenarios[path.stem.removeprefix("test_")] = classes[0]
    return scenarios


SCENARIOS = discover_scenarios()


@events.init_command_line_parser.add_listener
def arguments(parser, **kwargs):
    parser.add_argument("--scenario", choices=["all", *sorted(SCENARIOS)], default="configured_tax_exclusion",
                        help="Test scenario, or all to run discovered scenarios sequentially")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between sends per producer")
    parser.add_argument("--timeout", type=float, default=30.0, help="Completion/drain deadline in seconds")
    parser.add_argument("--avg-ms", type=float, default=500.0, help="Maximum successful end-to-end average")
    parser.add_argument("--p95-ms", type=float, default=1000.0, help="Maximum successful end-to-end p95")
    parser.add_argument("--p99-ms", type=float, default=1500.0, help="Maximum successful end-to-end p99")
    parser.add_argument("--min-rps", type=float, default=1.0, help="Minimum verified completions/sec including drain")
    parser.add_argument("--min-samples", type=int, default=10, help="Minimum submitted sample count")


@events.init.add_listener
def run_suite(environment, **kwargs):
    options = environment.parsed_options
    if options.scenario != "all":
        return
    if not isinstance(environment.runner, LocalRunner) or not options.headless or not options.run_time:
        print("TEST FAILED: scenario=all requires headless mode, a run-time, and a local runner", flush=True)
        raise SystemExit(1)
    raise SystemExit(run_all_scenarios(SCENARIOS, sys.argv[1:]))


@events.test_start.add_listener
def start(environment, **kwargs):
    if not isinstance(environment.runner, LocalRunner):
        environment.process_exit_code = 1
        save_summary(environment.parsed_options.scenario, False, "Requires a single local Locust process")
        print("TEST FAILED: scenarios currently support a single local Locust process", flush=True)
        gevent.spawn(environment.runner.quit)
        return
    run = environment.scenario_run = SCENARIOS[environment.parsed_options.scenario](environment)
    try:
        run.start()
    except Exception as exc:
        run.fatal = str(exc)
        environment.process_exit_code = 1
        save_summary(environment.parsed_options.scenario, False, f"Setup failed: {exc}")
        print(f"TEST FAILED: {environment.parsed_options.scenario} — setup: {exc}", flush=True)
        gevent.spawn(environment.runner.quit)


@events.test_stop.add_listener
def stop(environment, **kwargs):
    run = getattr(environment, "scenario_run", None)
    if run:
        try:
            run.stop()
        except Exception as exc:
            environment.process_exit_code = 1
            save_summary(environment.parsed_options.scenario, False, f"Reporting failed: {exc}")
            print(f"TEST FAILED: {environment.parsed_options.scenario} — reporting: {exc}", flush=True)
        finally:
            try:
                run.cleanup()
            except Exception as exc:
                environment.process_exit_code = 1
                save_summary(environment.parsed_options.scenario, False, f"Cleanup failed: {exc}")
                print(f"TEST FAILED: {environment.parsed_options.scenario} — cleanup: {exc}", flush=True)


class ScenarioUser(User):
    def wait_time(self):
        return self.environment.parsed_options.interval

    @task
    def run_scenario(self):
        self.environment.scenario_run.publish()
