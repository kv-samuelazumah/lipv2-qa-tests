"""Seed and verify an unstable lookup for its validating organisation."""
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "13-lip-v2"
sys.path.insert(0, str(APP))

from app.persistence.database import Database
from app.persistence.orm_models import LipV2LineItemSolution
from app.pre_agentic.normalize import build_lookup_hash, normalize_line_item, normalize_supplier

FIXTURE = json.loads((ROOT / "performance/fixtures/unstable_lookup_reused_by_validating_organisation.jsonl").read_text())
SUPPLIER = normalize_supplier(FIXTURE["supplierRaw"])
ITEM = normalize_line_item(FIXTURE["lineItemText"])
LOOKUP_HASH = build_lookup_hash(SUPPLIER, ITEM)
FIXTURE_ID = str(uuid5(NAMESPACE_URL, f"13-lip-v2/unstable-lookup/{LOOKUP_HASH}"))
SOLVED_FOR = [FIXTURE["orgId"]]
EXPECTED = {"resolved_by": "UNSTABLE_LOOKUP", "status_code": "SOLVED", "policy_code": None,
            "unspsc_code": "76111501", "unspsc_level": "COMMODITY", "selected_label": "Building cleaning services"}


def corpus_record():
    path = APP / "unspsc-search-corpus-v260801.1.jsonl"
    with path.open() as stream:
        for line in stream:
            row = json.loads(line)
            if row.get("code") == EXPECTED["unspsc_code"]:
                if (row.get("title"), row.get("tier"), row.get("selectable")) != ("Building cleaning services", "Commodity", True):
                    raise AssertionError("Cleaning service classification does not match the approved corpus")
                return {"file": path.name, "node_key": row["nodeKey"], "code": row["code"],
                        "level": row["tier"].upper(), "title": row["title"], "source": row["source"]}
    raise AssertionError("Cleaning service classification missing from corpus")


def verify_row(row, check_organisations=True):
    if row is None:
        raise AssertionError("Unstable lookup fixture is missing")
    required = {"lookup_hash": LOOKUP_HASH, "supplier_normalized": SUPPLIER,
                "line_item_normalized": ITEM, "stable": False, "unspsc_code": "76111501",
                "unspsc_level": "COMMODITY", "status_code": "SOLVED", "policy_code": None}
    for key, value in required.items():
        if getattr(row, key) != value:
            raise AssertionError(f"Unstable fixture has unexpected {key}; existing data was not overwritten")
    organisations = [str(org) for org in row.solved_for]
    if check_organisations and organisations != SOLVED_FOR:
        raise AssertionError("solved_for must contain only the validating organisation 111…")
    if (row.reasoning or {}).get("selected_label") != "Building cleaning services":
        raise AssertionError("Unstable fixture must retain the approved label")
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


def verify_pipeline(result, fixture_id=FIXTURE_ID):
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
    if reasoning.get("matched_row_id") != fixture_id or reasoning.get("stable") is not False:
        raise AssertionError("Result must identify the exact unstable fixture")
    if any(result.get(key) is not None for key in ("identify_search_result", "retrieval_result", "evaluation_result")):
        raise AssertionError("Unstable lookup unexpectedly entered an agentic stage")


def prepare(output):
    output.mkdir(parents=True, exist_ok=True)
    corpus = corpus_record()
    db = Database()
    created = False
    backup = None
    try:
        with db.get_session() as session:
            row = session.query(LipV2LineItemSolution).filter_by(lookup_hash=LOOKUP_HASH).one_or_none()
            if row is None:
                row = LipV2LineItemSolution(
                    id=UUID(FIXTURE_ID), lookup_hash=LOOKUP_HASH, supplier_raw=FIXTURE["supplierRaw"],
                    supplier_normalized=SUPPLIER, line_item_raw=FIXTURE["lineItemText"], line_item_normalized=ITEM,
                    stable=False, solved_for=[UUID(org) for org in SOLVED_FOR], unspsc_code=corpus["code"],
                    unspsc_level=corpus["level"], policy_code=None, status_code="SOLVED", source_type="SEED",
                    reasoning={"selected_label": corpus["title"], "corpus": corpus})
                session.add(row)
                session.flush()
                created = True
            else:
                existing = verify_row(row, check_organisations=False)
                if existing["solved_for"] != SOLVED_FOR:
                    backup = existing
                    (output / "lookup.backup.json").write_text(json.dumps(backup, indent=2))
                    row.solved_for = [UUID(org) for org in SOLVED_FOR]
                    session.flush()
            verify_row(row)
            session.commit()
    finally:
        db.close()
    before = verify()
    payload = {"orgId": FIXTURE["orgId"], "supplier": FIXTURE["supplierRaw"], "lineItemText": FIXTURE["lineItemText"]}
    command = [sys.executable, "main.py", "--input-json", json.dumps(payload), "--run-until-stage", "full"]
    env = dict(os.environ, DB_SCHEMA_SYNC="false", SEED_NON_UNSPSC_RULES="false",
               SEED_STABLE_LOOKUPS="false", SEED_UNSTABLE_LOOKUPS="false")
    evidence = {"command": command, "exit_code": None, "created_fixture": created,
                "approved_corpus": corpus, "before": before, "backup": backup}
    (output / "setup.json").write_text(json.dumps(evidence, indent=2, default=str))
    completed = subprocess.run(command, cwd=APP, env=env, capture_output=True, text=True, timeout=30)
    (output / "cli.stdout.log").write_text(completed.stdout)
    (output / "cli.stderr.log").write_text(completed.stderr)
    evidence["exit_code"] = completed.returncode
    (output / "setup.json").write_text(json.dumps(evidence, indent=2, default=str))
    if completed.returncode:
        raise AssertionError("Full CLI command failed; inspect cli.stderr.log")
    response = json.loads(completed.stdout.strip().splitlines()[-1])
    if response["input"]["org_id"] != FIXTURE["orgId"]:
        raise AssertionError("CLI did not run for validating organisation 111…")
    verify_pipeline(response["result"], before["fixture_id"])
    evidence["after_cli"] = verify()
    if evidence["after_cli"] != before:
        raise AssertionError("CLI changed the unstable fixture")
    (output / "setup.json").write_text(json.dumps(evidence, indent=2, default=str))
    return evidence


def restore(output):
    path = output / "setup.json"
    if not path.exists():
        return
    evidence = json.loads(path.read_text())
    backup = evidence.get("backup")
    if not backup:
        return
    if verify() != evidence["before"]:
        raise AssertionError("Fixture changed externally; refusing to overwrite it during restoration")
    db = Database()
    try:
        with db.get_session() as session:
            row = session.query(LipV2LineItemSolution).filter_by(lookup_hash=LOOKUP_HASH).one()
            row.solved_for = [UUID(org) for org in backup["solved_for"]]
            row.updated_at = datetime.fromisoformat(backup["row"]["updated_at"])
            session.commit()
            restored = verify_row(row, check_organisations=False)
            if restored != backup:
                raise AssertionError("Restored row differs from original backup")
            (output / "restoration.json").write_text(json.dumps({"restored": True, "original": restored}, indent=2))
    finally:
        db.close()
