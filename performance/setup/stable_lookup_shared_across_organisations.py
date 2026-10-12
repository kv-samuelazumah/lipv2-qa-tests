"""Seed and verify a corpus-backed stable lookup for a fourth organisation."""
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "13-lip-v2"
sys.path.insert(0, str(APP))

from app.persistence.database import Database
from app.persistence.orm_models import LipV2LineItemSolution
from app.pre_agentic.normalize import build_lookup_hash, normalize_line_item, normalize_supplier

FIXTURE = json.loads((ROOT / "performance/fixtures/stable_lookup_shared_across_organisations.jsonl").read_text())
SUPPLIER = normalize_supplier(FIXTURE["supplierRaw"])
ITEM = normalize_line_item(FIXTURE["lineItemText"])
LOOKUP_HASH = build_lookup_hash(SUPPLIER, ITEM)
FIXTURE_ID = str(uuid5(NAMESPACE_URL, f"13-lip-v2/stable-lookup/{LOOKUP_HASH}"))
SOLVED_FOR = [f"{digit * 8}-{digit * 4}-{digit * 4}-{digit * 4}-{digit * 12}" for digit in "123"]
EXPECTED = {"resolved_by": "STABLE_LOOKUP", "status_code": "SOLVED", "policy_code": None,
            "unspsc_code": "43212105", "unspsc_level": "COMMODITY", "selected_label": "Laser printers"}


def corpus_record():
    path = APP / "unspsc-search-corpus-v260801.1.jsonl"
    with path.open() as stream:
        for line in stream:
            row = json.loads(line)
            if row.get("code") == EXPECTED["unspsc_code"]:
                if (row.get("title"), row.get("tier"), row.get("selectable")) != ("Laser printers", "Commodity", True):
                    raise AssertionError("Laser printer classification does not match the approved corpus")
                return {"file": path.name, "node_key": row["nodeKey"], "code": row["code"],
                        "level": row["tier"].upper(), "title": row["title"], "source": row["source"]}
    raise AssertionError("Laser printer classification missing from corpus")


def verify_row(row):
    if row is None:
        raise AssertionError("Stable lookup fixture is missing")
    required = {"id": UUID(FIXTURE_ID), "lookup_hash": LOOKUP_HASH, "supplier_normalized": SUPPLIER,
                "line_item_normalized": ITEM, "stable": True, "unspsc_code": "43212105",
                "unspsc_level": "COMMODITY", "status_code": "SOLVED", "policy_code": None}
    for key, value in required.items():
        if getattr(row, key) != value:
            raise AssertionError(f"Stable fixture has unexpected {key}; existing data was not overwritten")
    organisations = [str(org) for org in row.solved_for]
    if len(organisations) != 3 or set(organisations) != set(SOLVED_FOR) or FIXTURE["orgId"] in organisations:
        raise AssertionError("solved_for must contain only organisations 111…, 222…, 333…")
    if (row.reasoning or {}).get("selected_label") != "Laser printers":
        raise AssertionError("Stable fixture must retain the approved label")
    return {"fixture_id": str(row.id), "lookup_hash": row.lookup_hash, "code": row.unspsc_code,
            "level": row.unspsc_level, "stable": row.stable, "solved_for": organisations,
            "requesting_org": FIXTURE["orgId"], "row": json.loads(json.dumps({
                column.name: getattr(row, column.key) for column in row.__table__.columns}, default=str))}


def verify():
    db = Database()
    try:
        with db.get_session() as session:
            return verify_row(session.query(LipV2LineItemSolution).filter_by(lookup_hash=LOOKUP_HASH).one_or_none())
    finally:
        db.close()


def verify_pipeline(result):
    if result.get("stage") != "PRE_AGENTIC_HIT":
        raise AssertionError("Expected pre-agentic short circuit")
    for branch in ("pre_agentic_result", "final_result"):
        for key, value in EXPECTED.items():
            if (result.get(branch) or {}).get(key) != value:
                raise AssertionError(f"{branch}: expected {key}={value!r}")
    pre = result["pre_agentic_result"]
    if pre.get("lookup_hash") != LOOKUP_HASH:
        raise AssertionError("Incorrect normalized supplier/item hash")
    reasoning = pre.get("reasoning") or {}
    if reasoning.get("matched_row_id") != FIXTURE_ID or reasoning.get("stable") is not True:
        raise AssertionError("Result must identify the exact stable fixture")
    if any(result.get(key) is not None for key in ("identify_search_result", "retrieval_result", "evaluation_result")):
        raise AssertionError("Stable lookup unexpectedly entered an agentic stage")


def prepare(output):
    output.mkdir(parents=True, exist_ok=True)
    corpus = corpus_record()
    db = Database()
    created = False
    try:
        with db.get_session() as session:
            row = session.query(LipV2LineItemSolution).filter_by(lookup_hash=LOOKUP_HASH).one_or_none()
            if row is None:
                row = LipV2LineItemSolution(
                    id=UUID(FIXTURE_ID), lookup_hash=LOOKUP_HASH, supplier_raw=FIXTURE["supplierRaw"],
                    supplier_normalized=SUPPLIER, line_item_raw=FIXTURE["lineItemText"], line_item_normalized=ITEM,
                    stable=True, solved_for=[UUID(org) for org in SOLVED_FOR], unspsc_code=corpus["code"],
                    unspsc_level=corpus["level"], policy_code=None, status_code="SOLVED", source_type="SEED",
                    reasoning={"selected_label": corpus["title"], "corpus": corpus})
                session.add(row)
                session.flush()
                created = True
            verify_row(row)
            session.commit()
    finally:
        db.close()
    before = verify()
    payload = {"orgId": FIXTURE["orgId"], "supplier": FIXTURE["supplierRaw"], "lineItemText": FIXTURE["lineItemText"]}
    command = [sys.executable, "main.py", "--input-json", json.dumps(payload), "--run-until-stage", "full"]
    env = dict(os.environ, DB_SCHEMA_SYNC="false", SEED_NON_UNSPSC_RULES="false",
               SEED_STABLE_LOOKUPS="false", SEED_UNSTABLE_LOOKUPS="false")
    completed = subprocess.run(command, cwd=APP, env=env, capture_output=True, text=True, timeout=30)
    (output / "cli.stdout.log").write_text(completed.stdout)
    (output / "cli.stderr.log").write_text(completed.stderr)
    evidence = {"command": command, "exit_code": completed.returncode, "created_fixture": created,
                "approved_corpus": corpus, "before": before}
    (output / "setup.json").write_text(json.dumps(evidence, indent=2, default=str))
    if completed.returncode:
        raise AssertionError("Full CLI command failed; inspect cli.stderr.log")
    response = json.loads(completed.stdout.strip().splitlines()[-1])
    if response["input"]["org_id"] != FIXTURE["orgId"]:
        raise AssertionError("CLI did not run for organisation 444…")
    verify_pipeline(response["result"])
    evidence["after_cli"] = verify()
    if evidence["after_cli"] != before:
        raise AssertionError("CLI changed the stable fixture")
    (output / "setup.json").write_text(json.dumps(evidence, indent=2, default=str))
    return evidence
