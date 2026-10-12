# 13-lip-v2

## Pre-Agentic Loop

This document formalizes the pre-agentic phase for LIP v2 before any agentic
retrieval or classification runs.

### Purpose

The pre-agentic loop exists to short-circuit expensive classification when the
line item has already been resolved:

1. for the current organisation only (`unstable`)
2. across enough organisations to be promoted (`stable`)
3. by a known non-UNSPSC regex/policy rule

## Priority Order

The priority order is fixed and must be evaluated in this exact sequence:

1. `unstable lookup`
2. `stable lookup`
3. `non_unspsc lookup`
4. enter the agentic loop only if none of the above resolve the item

## Core Definitions

### Lookup Hash

`lookup_hash` is the normalized identity for reuse.

Suggested source:

- normalized supplier or counterparty identity
- normalized line item raw text

Suggested formula:

```text
lookup_hash = sha256(normalized_supplier + "::" + normalized_line_item_raw)
```

### Stable

`stable` is derived from `solved_for`.

Rules:

- `stable = false` when `len(solved_for) < 3`
- `stable = true` when `len(solved_for) >= 3`

`stable` should be stored as a denormalized fast-lookup column, but
`solved_for` remains the source of truth.

## LineItemSolution Table

This table is the reuse cache for pre-agentic hits.

### Proposed Columns

| column | type | purpose |
|---|---|---|
| `id` | `uuid` | primary key |
| `lookup_hash` | `text` | normalized supplier + line item identity |
| `supplier_raw` | `text` | original supplier string used to build the hash |
| `supplier_normalized` | `text` | canonical supplier value used in lookup |
| `line_item_raw` | `text` | original line item text |
| `line_item_normalized` | `text` | normalized line item text used in lookup |
| `stable` | `boolean` | derived from `solved_for` cardinality |
| `solved_for` | `uuid[]` or `text[]` | organisations this solution has been validated for |
| `unspsc_code` | `varchar(8)` | stored UNSPSC result when applicable |
| `unspsc_level` | `text` | `SEGMENT`, `FAMILY`, `CLASS`, `COMMODITY` |
| `policy_code` | `text` | policy outcome such as `exclude_from_spend` |
| `status_code` | `text` | outcome status such as `SOLVED`, `REVIEW_REQUIRED`, `EXCLUDED` |
| `reasoning` | `jsonb` | stored explanation, evidence, provenance |
| `source_type` | `text` | `MANUAL`, `PROMOTED`, `AGENTIC`, `RULE` |
| `first_solved_at` | `timestamptz` | when the solution was first recorded |
| `last_solved_at` | `timestamptz` | last time this exact solution was confirmed |
| `created_at` | `timestamptz` | row creation timestamp |
| `updated_at` | `timestamptz` | row update timestamp |

### Notes

- `unspsc_code` must be a string, not a number.
- `unspsc_level` is the correct name for the taxonomy tier.
- `policy_code` and `status_code` are both stored because non-UNSPSC matches do
  not behave like ordinary solved classifications.
- `stable` must be recomputed whenever `solved_for` changes.

### Suggested Constraints

- unique index on `lookup_hash`
- check that `unspsc_code` is null only when the policy permits it
- check that `stable = true` implies `cardinality(solved_for) >= 3`

## Non-UNSPSC Rules Table

Regex rules should be data-driven, not hardcoded.

### Proposed Columns

| column | type | purpose |
|---|---|---|
| `id` | `uuid` | primary key |
| `rule_order` | `int` | evaluation order from the diagram |
| `label` | `text` | human-readable rule name |
| `pattern` | `text` | regex pattern |
| `policy_code` | `text` | policy result to apply |
| `status_code` | `text` | status result to apply |
| `fallback_unspsc_code` | `varchar(8)` | fallback UNSPSC bucket from the diagram |
| `fallback_unspsc_level` | `text` | usually `SEGMENT` or other configured tier |
| `active` | `boolean` | soft enable/disable |
| `notes` | `text` | operator documentation |
| `created_at` | `timestamptz` | row creation timestamp |
| `updated_at` | `timestamptz` | row update timestamp |

### Evaluation Contract

- rules are evaluated strictly by `rule_order`
- first match wins
- the rule returns the stored policy/status behavior exactly as configured

## Decision Table

| step | condition | action | continue? |
|---|---|---|---|
| 1 | `lookup_hash` hit and `stable = false` and `org_id in solved_for` | return stored `LineItemSolution` outcome | no |
| 2 | `lookup_hash` hit and `stable = true` | return stored `LineItemSolution` outcome | no |
| 3 | first regex rule matches in `non_unspsc_rules` | return stored rule outcome | no |
| 4 | no pre-agentic match | enter agentic loop | yes |

## Return Contract

Every pre-agentic branch should produce the same normalized output shape so the
rest of the pipeline does not care which branch resolved the item.

### Proposed Output Shape

```json
{
  "resolved_by": "UNSTABLE_LOOKUP",
  "status_code": "SOLVED",
  "policy_code": null,
  "unspsc_code": "44103103",
  "unspsc_level": "COMMODITY",
  "lookup_hash": "abc123",
  "reasoning": {
    "source_type": "PROMOTED",
    "matched_row_id": "uuid"
  }
}
```

Possible `resolved_by` values:

- `UNSTABLE_LOOKUP`
- `STABLE_LOOKUP`
- `NON_UNSPSC_RULE`
- `AGENTIC_LOOP`

## Pseudocode

```python
def run_pre_agentic_loop(org_id: str, supplier_raw: str, line_item_raw: str):
    supplier_normalized = normalize_supplier(supplier_raw)
    line_item_normalized = normalize_line_item(line_item_raw)
    lookup_hash = build_lookup_hash(supplier_normalized, line_item_normalized)

    unstable_hit = find_line_item_solution(
        lookup_hash=lookup_hash,
        stable=False,
        org_id=org_id,
    )
    if unstable_hit is not None:
        return normalize_solution_result(
            resolved_by="UNSTABLE_LOOKUP",
            solution=unstable_hit,
        )

    stable_hit = find_line_item_solution(
        lookup_hash=lookup_hash,
        stable=True,
    )
    if stable_hit is not None:
        return normalize_solution_result(
            resolved_by="STABLE_LOOKUP",
            solution=stable_hit,
        )

    rule_hit = find_first_non_unspsc_rule_match(line_item_raw)
    if rule_hit is not None:
        return normalize_rule_result(
            resolved_by="NON_UNSPSC_RULE",
            rule=rule_hit,
            lookup_hash=lookup_hash,
        )

    return None
```

## Promotion Logic

Promotion happens outside the pre-agentic loop.

### Invariant

Whenever `solved_for` changes:

```python
stable = len(solved_for) >= 3
```

### Promotion Example

1. first organisation solves `lookup_hash = X`
2. row stores `solved_for = [org_a]`, `stable = false`
3. second organisation confirms same outcome
4. row stores `solved_for = [org_a, org_b]`, `stable = false`
5. third organisation confirms same outcome
6. row stores `solved_for = [org_a, org_b, org_c]`, `stable = true`

## Implementation Notes

- prefer storing `solved_for` as organisation ids, not names
- if array membership queries become awkward, move `solved_for` to a join table
- non-UNSPSC rule evaluation should use normalized text and, where needed, raw
  text for exact phrase preservation
- pre-agentic outputs should be persisted with enough reasoning metadata for
  later review and promotion analysis

## Startup Behavior

`13-lip-v2` uses ORM-managed schema initialization on startup.

Install application dependencies into the root virtual environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r 13-lip-v2/requirements.txt
```

Initialize the database and enabled seeds without starting the queue worker:

```bash
cd 13-lip-v2
../.venv/bin/python main.py --bootstrap-only
```

Run the queue worker after starting the local services:

```bash
cd 13-lip-v2
../.venv/bin/python main.py
```

For local SQS, configure these values in `13-lip-v2/.env`:

```dotenv
AWS_REGION=eu-west-2
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_ENDPOINT_URL=http://localhost:4566
LINE_ITEM_INPUT_QUEUE_URL=http://sqs.eu-west-2.localhost.localstack.cloud:4566/000000000000/lip-v2-input
LINE_ITEM_RESULT_QUEUE_URL=http://sqs.eu-west-2.localhost.localstack.cloud:4566/000000000000/lip-v2-result
POST_OCR_QUEUE_URL=http://sqs.eu-west-2.localhost.localstack.cloud:4566/000000000000/lip-v2-post-ocr
```

The worker creates local queues on startup. If `DOCUMENT_METADATA_SQS_URL` or
`OCR_STATUS_QUEUE_URL` is configured, it takes precedence over
`LINE_ITEM_RESULT_QUEUE_URL`. The dummy credentials above are for LocalStack.

Run the unit tests from the repository root with live model credentials disabled:

```bash
DEEPSEEK_API_KEY= EVALUATE_CANDIDATES_API_KEY= WEB_REIDENTIFY_API_KEY= OPENAI_API_KEY= SERPER_API_KEY= .venv/bin/python -m unittest discover -s 13-lip-v2/tests
```

## Local Elasticsearch

`13-lip-v2` has its own Docker Compose setup for local Elasticsearch.

Start Postgres, Elasticsearch, and LocalStack SQS:

```bash
cd 13-lip-v2
docker compose up -d
```

Start Postgres, Elasticsearch, LocalStack SQS, and Kibana:

```bash
cd 13-lip-v2
docker compose --profile kibana up -d
```

Default local endpoints:

- Postgres: `localhost:5432`
- Elasticsearch: `http://localhost:9200`
- LocalStack SQS: `http://localhost:4566`
- Kibana: `http://localhost:5601`

The default local `.env` values are:

- `POSTGRES_DB=unspsc`
- `POSTGRES_USER=postgres`
- `POSTGRES_PASSWORD=postgres`
- `POSTGRES_HOST=localhost`
- `POSTGRES_PORT=5432`
- `ELASTICSEARCH_BASE_URL=http://localhost:9200`
- `ELASTICSEARCH_UNSPSC_INDEX=lip-v2-unspsc`

This compose file disables Elastic security for local development so no
Elasticsearch username/password or API key is required.

## UNSPSC Corpus Indexing

`unspsc-search-corpus-v260801.1.jsonl` is the source corpus for lexical and semantic
search indexing. It is not pre-embedded.

To build the Elasticsearch index from this corpus:

```bash
cd 13-lip-v2
python3 main.py --index-unspsc-corpus unspsc-search-corpus-v260801.1.jsonl
```

Required env vars for indexing:

- `OPENAI_API_KEY`
- `ELASTICSEARCH_BASE_URL`
- `ELASTICSEARCH_UNSPSC_INDEX`

Optional env vars for indexing:

- `OPENAI_EMBEDDING_MODEL`
- `OPENAI_BASE_URL`
- `ELASTICSEARCH_API_KEY`
- `ELASTICSEARCH_USERNAME`
- `ELASTICSEARCH_PASSWORD`
- `UNSPSC_IMPORT_BATCH_SIZE`
- `SUPPLIER_MATCH_MIN_SIMILARITY`

Environment:

- `DB_SCHEMA_SYNC=true`:
  - create missing tables from ORM models
  - ensure required indexes exist
- `DB_SCHEMA_SYNC=false`:
  - initialize extensions only
  - do not modify table structure
- `SEED_NON_UNSPSC_RULES=true`:
  - upsert the initial non-UNSPSC rule dataset on startup
  - useful after schema sync in local development
- `SUPPLIER_MATCH_MIN_SIMILARITY=0.75`:
  - minimum similarity allowed for fuzzy supplier-to-company enrichment matches
  - used only after exact current-name and previous-name matches fail

The database connection uses the same `POSTGRES_*` environment variables as the
old `06-line-item-processor`.

## Companies House SIC Enrichment

SIC enrichment sits between the pre-agentic loop and the Identify/Search prompt.

Flow:

1. pre-agentic miss
2. supplier name enrichment against the Companies House cache
3. inject `supplier_sic_label` into the Identify/Search invoice context
4. continue into the agentic loop

Import the monthly Companies House bulk dataset with:

```bash
cd 13-lip-v2
python3 main.py \
  --import-companies-house companies-house.csv \
  --companies-house-source-month 2026-07
```

For large files, progress is printed every `10,000` scanned rows by default.
Override that with:

```bash
cd 13-lip-v2
python3 main.py \
  --import-companies-house companies-house.csv \
  --companies-house-source-month 2026-07 \
  --companies-house-progress-every 5000
```

Progress lines include:

- scanned rows
- imported rows
- skipped rows
- elapsed seconds
- imported rows per second

Default expected columns:

- `CompanyName`
- `CompanyNumber`
- `SICCode.SicText_1`
- `SICCode.SicText_2`
- `SICCode.SicText_3`
- `SICCode.SicText_4`

Each `SICCode.SicText_*` value is parsed from the Companies House format:

- `70100 - Activities of head offices`
- `45112 - Sale of used cars and light motor vehicles`

The importer stores these as:

- `sic_codes`: `["70100"]`
- `sic_labels`: `["Activities of head offices"]`

It also captures:

- `PreviousName_1.CompanyName` ... `PreviousName_10.CompanyName`
- `CompanyStatus`
- `CompanyCategory`
- `CountryOfOrigin`
- `IncorporationDate`
- `DissolutionDate`

Optional VAT column:

```bash
cd 13-lip-v2
python3 main.py \
  --import-companies-house companies-house.csv \
  --companies-house-source-month 2026-07 \
  --companies-house-vat-column vat_number
```

If your file uses different headers, override them with:

- `--companies-house-company-name-column`
- `--companies-house-number-column`
- `--companies-house-sic-codes-column`
- `--companies-house-sic-labels-column`

During manual pipeline testing, if the input payload does not already provide
`supplierSicLabel`, `13-lip-v2` now attempts to populate it from the imported
Companies House cache automatically.

## Manual Stage Testing

You can run a line item through specific parts of the processor for manual
testing.

Available stages:

- `pre_agentic`
- `identify`
- `search`
- `evaluate`
- `web_search`
- `web_reidentify`
- `full`

Use `--skip-pre-agentic` when you want to bypass the cache/rule layer and force
testing of the agentic stages.

### Pre-Agentic Only

```bash
cd 13-lip-v2
python3 main.py --input-json '{
  "orgId": "11111111-1111-1111-1111-111111111111",
  "supplier": "Acme Ltd",
  "lineItemText": "VAT"
}' --run-until-stage pre_agentic
```

### Identify Only

```bash
cd 13-lip-v2
python3 main.py --input-json '{
  "orgId": "11111111-1111-1111-1111-111111111111",
  "supplier": "Acme Ltd",
  "lineItemText": "Notebook",
  "unitPrice": 1200
}' --run-until-stage identify --skip-pre-agentic
```

### Search Only

```bash
cd 13-lip-v2
python3 main.py --input-json '{
  "orgId": "11111111-1111-1111-1111-111111111111",
  "supplier": "Acme Ltd",
  "lineItemText": "Notebook",
  "unitPrice": 1200
}' --run-until-stage search --skip-pre-agentic
```

### Evaluate Only

```bash
cd 13-lip-v2
python3 main.py --input-json '{
  "orgId": "11111111-1111-1111-1111-111111111111",
  "supplier": "Acme Ltd",
  "lineItemText": "Notebook",
  "unitPrice": 1200
}' --run-until-stage evaluate --skip-pre-agentic
```

### Web Search Only

```bash
cd 13-lip-v2
python3 main.py --input-json '{
  "orgId": "11111111-1111-1111-1111-111111111111",
  "supplier": "Acme Ltd",
  "lineItemText": "XJ-44592"
}' --run-until-stage web_search --skip-pre-agentic
```

### Web Re-Identify Only

```bash
cd 13-lip-v2
python3 main.py --input-json '{
  "orgId": "11111111-1111-1111-1111-111111111111",
  "supplier": "Acme Ltd",
  "lineItemText": "XJ-44592"
}' --run-until-stage web_reidentify --skip-pre-agentic
```

### Full Agentic Flow

```bash
cd 13-lip-v2
python3 main.py --input-json '{
  "orgId": "11111111-1111-1111-1111-111111111111",
  "supplier": "Acme Ltd",
  "lineItemText": "Notebook",
  "unitPrice": 1200
}' --run-until-stage full --skip-pre-agentic
```

### `resolved_by` Values

Pre-agentic results:

- `UNSTABLE_LOOKUP`
- `STABLE_LOOKUP`
- `NON_UNSPSC_RULE`

Manual stage-testing checkpoints:

- `PRE_AGENTIC_MISS`
- `PRE_AGENTIC_SKIPPED`
- `AGENTIC_IDENTIFY_SEARCH`
- `AGENTIC_UNSPSC_SEARCH`
- `AGENTIC_EVALUATE_CANDIDATES`
- `AGENTIC_WEB_SEARCH`
- `AGENTIC_WEB_REIDENTIFY`

Final agentic outcomes:

- `AGENTIC_EVALUATION_SELECT_CANDIDATE`
- `AGENTIC_EVALUATION_SELECT_PARENT`
- `AGENTIC_RESEARCH_NO_NEW_QUERIES`
- `AGENTIC_RESEARCH_EXHAUSTED`
- `AGENTIC_WEB_SEARCH_BLOCKED`
- `AGENTIC_WEB_REIDENTIFY_UNAVAILABLE`
- `AGENTIC_EVALUATION_UNABLE_TO_RESOLVE`

For the richer UNSPSC embeddings table:

- `text-embedding-3-large` uses 3072 dimensions
- pgvector ANN indexes in this setup are not created for vectors above 2000 dimensions
- startup therefore creates only the lexical trigram index for the embeddings table
- if you need ANN vector indexing later, use a smaller embedding model or change
  the vector storage/indexing approach

## Run Pre-Agentic Resolution

You can also run the pre-agentic loop directly from the CLI:

```bash
cd 13-lip-v2
python3 main.py \
  --org-id 11111111-1111-1111-1111-111111111111 \
  --supplier "Acme Ltd" \
  --line-item "VAT"
```

Behavior:

- initializes database/bootstrap on startup
- optionally seeds non-UNSPSC rules when `SEED_NON_UNSPSC_RULES=true`
- optionally seeds a sample stable lookup when `SEED_STABLE_LOOKUPS=true`:
  supplier `Acme Ltd`, line item `Notebook`, UNSPSC code `43211503` (`COMMODITY`),
  status `SOLVED`, and three sample organisation IDs in `solved_for`
- stable lookup seeding inserts missing entries only and preserves existing solutions
- optionally seeds a sample unstable lookup when `SEED_UNSTABLE_LOOKUPS=true`:
  supplier `Acme Ltd`, line item `Local area trucking services`, UNSPSC code
  `78101801` (`COMMODITY`), status `SOLVED`, and only organisation
  `11111111-1111-1111-1111-111111111111` in `solved_for` (`stable=false`)
- unstable lookup seeding inserts missing entries only and preserves existing solutions
- runs the Postgres-backed pre-agentic loop
- prints normalized JSON output or `null`

You can also test with a queue-like JSON payload:

```bash
cd 13-lip-v2
python3 main.py --input-json '{
  "orgId": "11111111-1111-1111-1111-111111111111",
  "supplier": "Acme Ltd",
  "lineItemText": "VAT"
}'
```

Accepted JSON keys:

- org: `orgId`, `org_id`
- supplier: `supplier`, `supplierRaw`, `supplier_raw`, `vendorName`, `vendor_name`, `counterparty`, `counterpartyName`
- line item: `lineItemText`, `line_item_text`, `lineItemRaw`, `line_item_raw`, `description`

You can also pass a JSON array to test multiple payloads in one command.

## Identify And Search

The first post-pre-agentic agentic step is modeled as a strict request/response
contract:

- request/response models: `app/identify_search/models.py`
- prompt builder: `app/identify_search/prompt.py`
- DeepSeek-compatible client scaffold: `app/identify_search/client.py`

This step is responsible for:

- understanding the target line identity
- recording evidence usage
- generating bounded UNSPSC retrieval queries

DeepSeek configuration:

- `DEEPSEEK_API_KEY`
- `DEEPSEEK_BASE_URL` default: `https://api.deepseek.com`
- `IDENTIFY_SEARCH_MODEL` default: `deepseek-chat`

## UNSPSC Search Tool

The retrieval tool is implemented under `app/search/`:

- `models.py`
- `fusion.py`
- `embedding_client.py`
- `elasticsearch_client.py`
- `service.py`

Component split:

- DeepSeek:
  - identify-and-search prompt generation
- OpenAI:
  - query embeddings for semantic retrieval
- Elasticsearch:
  - exact search
  - BM25 search
  - semantic/vector search
  - source results for RRF fusion

Environment:

- `OPENAI_API_KEY`
- `OPENAI_EMBEDDING_MODEL` default: `text-embedding-3-large`
- `OPENAI_BASE_URL` optional
- `ELASTICSEARCH_BASE_URL` default: `http://localhost:9200`
- `ELASTICSEARCH_UNSPSC_INDEX` default: `lip-v2-unspsc`
- `ELASTICSEARCH_API_KEY` optional
- `ELASTICSEARCH_USERNAME` optional
- `ELASTICSEARCH_PASSWORD` optional
