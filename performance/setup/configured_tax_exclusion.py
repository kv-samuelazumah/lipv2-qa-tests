"""Read-only database preconditions and full CLI evidence for the VAT case."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "13-lip-v2"
sys.path.insert(0, str(APP))

from app.persistence.database import Database
from app.persistence.orm_models import LipV2LineItemSolution, LipV2NonUnspscRule
from app.pre_agentic.normalize import build_lookup_hash, normalize_line_item, normalize_supplier

FIXTURE = json.loads((ROOT / "performance" / "fixtures" / "configured_tax_exclusion.jsonl").read_text().strip())
LOOKUP_HASH = build_lookup_hash(
    normalize_supplier(FIXTURE["supplierRaw"]), normalize_line_item(FIXTURE["lineItemText"])
)
EXPECTED = {
    "resolved_by": "NON_UNSPSC_RULE", "status_code": "EXCLUDED",
    "policy_code": "exclude_from_spend", "unspsc_code": "-1000", "unspsc_level": "SEGMENT",
}


def verify_pipeline(result):
    if result.get("stage") != "PRE_AGENTIC_HIT":
        raise AssertionError(f"Unexpected stage: {result.get('stage')}")
    for key, value in EXPECTED.items():
        if (result.get("final_result") or {}).get(key) != value:
            raise AssertionError(f"Expected {key}={value!r}")
    pre = result.get("pre_agentic_result") or {}
    if pre.get("lookup_hash") != LOOKUP_HASH:
        raise AssertionError("Normalized lookup hash differs")
    if (pre.get("reasoning") or {}).get("matched_rule_label") != "VAT":
        raise AssertionError("Expected the configured VAT rule")
    for key in ("identify_search_result", "retrieval_result", "evaluation_result"):
        if result.get(key) is not None:
            raise AssertionError(f"Agentic stage unexpectedly ran: {key}")


def verify():
    db = Database()
    try:
        with db.get_session() as session:
            rows = session.query(LipV2LineItemSolution).filter_by(lookup_hash=LOOKUP_HASH).all()
            if rows:
                raise AssertionError("Matching lookup exists; remove it through your QA preparation before testing")
            rules = session.query(LipV2NonUnspscRule).filter_by(active=True).order_by(
                LipV2NonUnspscRule.rule_order
            ).all()
            first = next((r for r in rules if re.search(r.pattern, "vat", re.IGNORECASE)), None)
            if first is None or first.label != "VAT":
                raise AssertionError("The first matching active rule must be VAT")
            for column, value in {
                "policy_code": "exclude_from_spend", "status_code": "EXCLUDED",
                "fallback_unspsc_code": "-1000", "fallback_unspsc_level": "SEGMENT",
            }.items():
                if getattr(first, column) != value:
                    raise AssertionError(f"VAT rule has unexpected {column}")
            return {"lookup_hash": LOOKUP_HASH, "matching_lookup_rows": 0,
                    "matched_rule_id": str(first.id), "matched_rule_order": first.rule_order}
    finally:
        db.close()


def prepare(output):
    output.mkdir(parents=True, exist_ok=True)
    before = verify()
    payload = {"orgId": FIXTURE["orgId"], "supplier": FIXTURE["supplierRaw"], "lineItemText": "VAT"}
    command = [sys.executable, "main.py", "--input-json", json.dumps(payload), "--run-until-stage", "full"]
    env = dict(os.environ, DB_SCHEMA_SYNC="false", SEED_NON_UNSPSC_RULES="false",
               SEED_STABLE_LOOKUPS="false", SEED_UNSTABLE_LOOKUPS="false")
    completed = subprocess.run(command, cwd=APP, env=env, capture_output=True, text=True, timeout=30)
    (output / "cli.stdout.log").write_text(completed.stdout)
    (output / "cli.stderr.log").write_text(completed.stderr)
    evidence = {"command": command, "exit_code": completed.returncode, "before": before}
    (output / "setup.json").write_text(json.dumps(evidence, indent=2))
    if completed.returncode:
        raise AssertionError(f"CLI failed; see {output / 'cli.stderr.log'}")
    result = json.loads(completed.stdout.strip().splitlines()[-1])["result"]
    verify_pipeline(result)
    evidence["after_cli"] = verify()
    (output / "setup.json").write_text(json.dumps(evidence, indent=2))
    return evidence
