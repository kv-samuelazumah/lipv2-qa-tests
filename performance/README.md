# LIP v2 worker performance tests

The configured tax exclusion scenario uses the existing folders:

```text
performance/
  common.py
  fixtures/configured_tax_exclusion.jsonl
  setup/configured_tax_exclusion.py
  tests/test_configured_tax_exclusion.py
  locustfile.py
```

The setup file checks database preconditions and captures a full CLI run. The
fixture holds the input. The test file defines VAT result and stage-log checks
and includes unit tests for its assertions. `common.py` handles worker startup,
SQS publishing, result collection, cleanup, and performance reports.
`locustfile.py` discovers tests and runs the scenario selected in `locust.conf`.

## Run

From the repository root:

```bash
.venv/bin/python -m pip install -r requirements.txt
docker compose -f 13-lip-v2/docker-compose.yml up -d
.venv/bin/locust
```

The root `locust.conf` loads automatically when running from the repository root.
Edit it to change users, spawn rate, run duration, publishing interval, timeout,
and performance thresholds. It currently specifies ten producers, two new
producers per second, a 60-second run, and a one-second publishing interval.
Command-line arguments override file settings, for example:

```bash
.venv/bin/locust --users 2 --run-time 30s
```

For the browser UI, set `headless = false` in `locust.conf`, then run the same
short command and open `http://localhost:8089`.

See [Locust configuration files](https://docs.locust.io/en/stable/configuration.html#configuration-file).

This test starts and stops one application worker automatically. It uses three
uniquely named LocalStack queues; existing workers and application queues are
not used. Each user is a producer sending approximately one message per second
at the default interval, independently of completion latency. Start with two
producers, then raise `-u` to find when the single worker develops a backlog.
Distributed Locust runs are not supported by this scenario.

The test reads `13-lip-v2/.env`. PostgreSQL must already be bootstrapped and
`AWS_ENDPOINT_URL` must point to local LocalStack. Live model credentials are
unnecessary for this exclusion path. Setup validates the existing VAT rule and
fails if any lookup exists for the normalized fixture hash. It does not delete
lookups or overwrite rules. Prepare the database before rerunning if validation
fails; do not change rule or lookup state during a run.

## Selecting and adding scenarios

The root `locust.conf` defaults to `scenario = all`. Run `.venv/bin/locust` to
execute all discovered scenarios sequentially, each for the configured duration
and with its own worker, queues, and report. An individual failure does not skip
later scenarios. The terminal prints each verdict and an overall verdict; the
command exits with code 1 if any scenario fails. Running all scenarios requires
headless mode and a finite `run-time`.

Set `scenario = configured_tax_exclusion` to select one test, or override it with
`.venv/bin/locust --scenario configured_tax_exclusion`. Uncomment only one
`scenario` entry in the configuration file.

To add another test, create its fixture in `fixtures/`, its preparation code in
`setup/`, and `tests/test_<scenario>.py`. The test file must define one
`WorkerScenario` subclass with its fixture, setup/verification hooks, expected
result checks, and worker-log checks, following the existing VAT test. The runner
discovers it automatically using the filename without `test_`. Files containing
only unit tests are skipped. No VAT-specific options are required by the runner.

`interval`, `timeout`, `avg-ms`, `p95-ms`, `p99-ms`, `min-rps`, and `min-samples` apply to whichever
scenario is selected. Set appropriate acceptance thresholds for each run.
Available scenarios are `configured_tax_exclusion`,
`stable_lookup_shared_across_organisations`, and
`unstable_lookup_reused_by_validating_organisation`. Mixed workloads are not implemented.
The report records the selected scenario.

### Stable lookup shared across organisations

```bash
.venv/bin/locust --scenario stable_lookup_shared_across_organisations
```

This scenario seeds or verifies `Acme Ltd / Laser printers`, with corpus code
`43212105` at `COMMODITY` level. It uses the application's deterministic stable
seed ID, recorded alongside the exact hash/code/level and corpus provenance in
`setup.json`. An existing conflicting lookup causes setup to fail without
overwriting it. The approved seed remains in the QA database for repeat runs.

Only organisations `11111111-1111-1111-1111-111111111111`,
`22222222-2222-2222-2222-222222222222`, and
`33333333-3333-3333-3333-333333333333` are in `solved_for`. CLI preflight and every
load request use organisation `44444444-4444-4444-4444-444444444444`.
The expected result is `PRE_AGENTIC_HIT`, `STABLE_LOOKUP`, `SOLVED`, no policy,
and the exact seeded row ID/category/label, without identify/search/evaluation.
Both output events, stage logs, and the entire database row are checked. The
requesting organisation must not be added to `solved_for` during the run.

Evidence and performance reports are saved under `results/stable-shared-<id>/`.
Shared latency, throughput, timeout, duplicate, sample-count, and queue-drain gates
apply using the settings in `locust.conf`.

### Unstable lookup reused by validating organisation

```bash
.venv/bin/locust --scenario unstable_lookup_reused_by_validating_organisation
```

Setup seeds or verifies `Clearway Cleaning Services / Building cleaning services`
with corpus-backed code `76111501`, level `COMMODITY`, status `SOLVED`,
`stable=false`, and `solved_for` containing only organisation
`11111111-1111-1111-1111-111111111111`. The exact fixture ID, lookup hash, corpus
source, and complete database row are recorded in `setup.json`. Conflicting
classification data fails setup without being overwritten. If a matching unstable
row has additional validating organisations, setup records its actual ID, backs
it up to `lookup.backup.json`, and temporarily restricts `solved_for` to 111….
Cleanup restores the original membership and timestamp after checking that the
test fixture was not changed externally; `restoration.json` records the result.
A newly inserted fixture is retained for repeat runs.

The CLI and load messages use the validating organisation 111…. Expected output
is `PRE_AGENTIC_HIT`, `UNSTABLE_LOOKUP`, the exact fixture ID, code `76111501`,
and no agentic stages. Both worker output events and stage logs are verified.
The fixture, including `stable=false`, `solved_for`, and timestamps, must remain
unchanged. Reports are under `results/unstable-validating-<id>/`; shared performance
gates apply. This scenario is automatically included in `scenario = all`.

## Expected results for configured tax exclusion

- First matching active rule: VAT, with the configured `-1000` exclusion fallback.
- Pipeline stage: `PRE_AGENTIC_HIT`; resolution: `NON_UNSPSC_RULE`.
- Status: `EXCLUDED`; policy: `exclude_from_spend`; tier: `SEGMENT`.
- Identify, retrieval, and evaluation results remain null.
- The worker emits matching result and post-OCR events with category `-1000`.
- Every event retains the submitted organisation, transaction, document,
  line-item index/text, and unique correlation ID.
- No lookup exists for this supplier/item hash before or after the run.
- All submitted messages produce both verified output events; no duplicates or
  timeouts occur, and the input queue drains.

The worker currently reports `solvedBy=OPENAI` for every result with a category
code, including rule exclusions. The test checks that event contract and uses
`reasoning.final_result.resolved_by` to prove the VAT rule handled the message.
Every request includes `uploadedDocumentId`, which the post-OCR publisher requires.

## Performance evaluation and evidence

Each run creates an ignored `results/<scenario-prefix>-<id>/` directory
(`results/vat-<id>/` for the VAT test) containing:

- `setup.json`, `cli.stdout.log`, `cli.stderr.log`: full-command exit code,
  output, and database checks.
- `worker.stdout.log`, `worker.stderr.log`: worker startup and stage evidence.
- `events.jsonl`: both observed output events for each correlation ID.
- `report.json`: functional checks, average/P95/P99, verified completions/second,
  successful/failed executions, failure rate, drain duration, duplicate checks, and verdict.

Locust records one end-to-end measurement per workflow, with no separate
submission metric that would double-count executions in the aggregate row.
End-to-end timing starts before publishing and ends after both output events are
observed; it includes queue waiting, processing, publishing, and collector delay.
The collector polls approximately every 20 ms, so very fast processing has a
measurement floor. Completion throughput includes the drain period.
Startup and CLI preflight are excluded from these
reported durations. Percentiles use successful verified completions only;
failures independently fail the run. LocalStack results describe this local
system, not AWS production capacity.

The timing and throughput limits are provisional: average at most 500 ms,
p95 at most 1000 ms, p99 at most 1500 ms, and at least one verified completed
workflow/second. Zero failures are allowed. Set `avg-ms`, `p95-ms`, `p99-ms`,
`min-rps`, and `min-samples` in `locust.conf` to your agreed acceptance criteria
(the config requires 20 messages; the parser default is ten). All four performance
thresholds affect the verdict; missing successful samples fail the timing gates. Missing completions expire after `--timeout` seconds (default 30).
The process exits with code 1 if any functional or performance gate fails.
The terminal displays a table with test name, `PASS`/`FAIL`, and failure reasons,
plus successful/failed message counts, failure rate, average/P95/P99 latency, and verified throughput. All-scenario runs end
with a combined table. Long reasons wrap across lines; the report path points to
the full evidence.
`failure_rate_percent` is failed executions divided by submitted executions,
multiplied by 100, after outstanding messages have completed or timed out.
No submitted executions produces `null` in the report and `unavailable` in the
terminal. Setup failures are reported separately; any failed execution still
fails the run.
Only queues created by this run are deleted during cleanup; evidence is retained.

Lifecycle and custom request reporting use the
[Locust event hooks](https://docs.locust.io/en/stable/api.html#event-hooks).
