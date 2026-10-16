"""Prepare real database records for each scenario and restore them after the run."""
import copy
import json
import re
import sys
from datetime import datetime
from functools import lru_cache
from uuid import UUID, uuid4

from sqlalchemy import text

from performance.common import APP

sys.path.insert(0, str(APP))
from app.persistence.database import Database
from app.persistence.orm_models import LipV2LineItemSolution, LipV2NonUnspscRule
from app.persistence.seeds.non_unspsc_rules import NON_UNSPSC_RULE_SEEDS
from app.pre_agentic.normalize import build_lookup_hash, normalize_line_item, normalize_supplier

ORG1 = "11111111-1111-1111-1111-111111111111"
ORG2 = "22222222-2222-2222-2222-222222222222"
ORG3 = "33333333-3333-3333-3333-333333333333"
ORG4 = "44444444-4444-4444-4444-444444444444"
LOCK_ID = 0x4C49505141


@lru_cache
def corpus_record(code):
    with (APP / "unspsc-search-corpus-v260801.1.jsonl").open() as source:
        for line in source:
            row = json.loads(line)
            if row["code"] == code:
                return row
    raise ValueError(f"Required UNSPSC code {code} is missing from the application corpus")


def snapshot(row):
    return {column.name: copy.deepcopy(getattr(row, column.name)) for column in row.__table__.columns}


def payload_hash(payload):
    return build_lookup_hash(normalize_supplier(payload.get("supplier", "")),
                             normalize_line_item(payload.get("lineItemText") or ""))


def database_state(payload):
    """Read the prepared state without changing it."""
    db = Database()
    try:
        with db.get_session() as session:
            row = session.query(LipV2LineItemSolution).filter_by(lookup_hash=payload_hash(payload)).first()
            saved = None if row is None else {
                "id": str(row.id), "lookup_hash": row.lookup_hash, "stable": row.stable,
                "solved_for": [str(org) for org in row.solved_for], "code": row.unspsc_code,
                "level": row.unspsc_level, "status": row.status_code, "policy": row.policy_code,
                "label": (row.reasoning or {}).get("selected_label"),
            }
            rules = session.query(LipV2NonUnspscRule).filter_by(active=True).order_by(
                LipV2NonUnspscRule.rule_order).all()
            matched = next((r for r in rules if re.search(r.pattern, payload.get("lineItemText") or "", re.I)), None)
            rule = None if matched is None else {
                "id": str(matched.id), "order": matched.rule_order, "label": matched.label,
                "status": matched.status_code, "policy": matched.policy_code,
                "code": matched.fallback_unspsc_code, "level": matched.fallback_unspsc_level,
            }
            return {"row": saved, "rule": rule}
    finally:
        db.close()


def case_payloads(inputs):
    payloads = []
    for item in inputs:
        if isinstance(item, str):
            try:
                item = json.loads(item)
            except json.JSONDecodeError:
                # Invalid-JSON case still checks this supplier/item for unwanted persistence.
                item = dict(supplier="Workplace Safety Supplies", lineItemText="Safety helmet")
        payloads.extend(item if isinstance(item, list) else [item])
    payloads = list({payload_hash(p): p for p in payloads}.values())
    return payloads


def case_rules(spec, inputs):
    mode = spec["mode"]
    required = []
    if mode == "rule":
        label = spec["rule"]["label"]
        required = [dict(seed) for seed in NON_UNSPSC_RULE_SEEDS if seed["label"] == label]
        if not required:
            raise ValueError(f"No application rule definition found for {inputs[0]['lineItemText']}")
    elif mode == "batch":
        required = [dict(seed) for seed in NON_UNSPSC_RULE_SEEDS if seed["label"] == "PAYE"]
    if spec.get("conflicting_rule"):
        required = [dict(rule_order=900036, label="Lookup precedence exclusion",
                         pattern="^" + re.escape(inputs[0]["lineItemText"]) + "$",
                         policy_code="exclude_from_spend", status_code="EXCLUDED",
                         fallback_unspsc_code="-1000", fallback_unspsc_level="SEGMENT")]
    return required


class DataPreparation:
    def __init__(self, run):
        self.run = run
        self.db = None
        self.lock = None
        self.backup = None
        self.applied = False
        self.lock_owned = False

    def prepare(self):
        case = self.run.case
        spec, inputs = case.spec, case.inputs

        # Preserve sequential dependencies inside a case; prepare only once before its first command.
        payloads = case_payloads(inputs)
        hashes = [payload_hash(p) for p in payloads]
        required = case_rules(spec, inputs)
        orders = {rule["rule_order"] for rule in required}

        self.db = Database()
        self.lock = self.db.engine.connect()
        self.lock_owned = self.lock.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_ID}).scalar()
        if not self.lock_owned:
            raise RuntimeError("Another QA scenario is preparing or using the test data")
        self.lock.commit()
        with self.db.get_session() as session:
            rules = session.query(LipV2NonUnspscRule).all()
            affected_rules = [r for r in rules if r.rule_order in orders or r.active and any(
                re.search(r.pattern, p.get("lineItemText") or "", re.I) for p in payloads)]
            orders.update(r.rule_order for r in affected_rules)
            rows = session.query(LipV2LineItemSolution).filter(LipV2LineItemSolution.lookup_hash.in_(hashes)).all()
            self.backup = dict(hashes=hashes, rule_orders=sorted(orders),
                               database=self.database_identity(),
                               solutions=[snapshot(row) for row in rows], rules=[snapshot(r) for r in affected_rules])
            (self.run.output / "database-backup.json").write_text(json.dumps(self.backup, default=str, indent=2))

            # Clear just this case's lookup keys, including records created by a previous run.
            for row in rows:
                session.delete(row)
            for rule in affected_rules:
                rule.active = False
            session.flush()
            self.activate_rules(session, required)
            self.prepare_lookup(session, spec, inputs[0])
            session.commit()
            self.applied = True

    @staticmethod
    def activate_rules(session, required):
        for values in required:
            values = {key: value for key, value in values.items() if key != "id"}
            rule = session.query(LipV2NonUnspscRule).filter_by(rule_order=values["rule_order"]).first()
            if rule is None:
                rule = LipV2NonUnspscRule(id=uuid4(), **values)
                session.add(rule)
            else:
                for key, value in values.items():
                    setattr(rule, key, value)
            rule.active = True

    def prepare_lookup(self, session, spec, first):
        mode = spec["mode"]
        if mode == "lookup":
            code = spec.get("code") or "43212105"
            orgs = spec.get("solved_for") or [ORG1]
            stable = spec.get("stable", False)
            if stable and len(orgs) < 3:
                orgs = [ORG1, ORG2, ORG3]
            self.save_lookup(session, first, code, orgs)
        elif mode in ("isolation", "change"):
            self.save_lookup(session, first, spec["old_code"], spec["old_orgs"])
        elif mode == "batch":
            self.save_lookup(session, first[2], "44121704", [ORG1, ORG2, ORG3])

    @staticmethod
    def save_lookup(session, payload, code, orgs):
        corpus = corpus_record(code)
        session.add(LipV2LineItemSolution(
            id=uuid4(), lookup_hash=payload_hash(payload), supplier_raw=payload["supplier"],
            supplier_normalized=normalize_supplier(payload["supplier"]),
            line_item_raw=payload["lineItemText"], line_item_normalized=normalize_line_item(payload["lineItemText"]),
            solved_for=[UUID(org) for org in orgs], stable=len(set(orgs)) >= 3,
            unspsc_code=code, unspsc_level=corpus["tier"].upper(), status_code="SOLVED", policy_code=None,
            source_type="QA_SETUP", reasoning={"selected_label": corpus["title"]},
        ))

    def database_identity(self):
        config = self.db.db_config
        return dict(host=config.host, port=config.port, dbname=config.dbname, user=config.user)

    def restore(self):
        try:
            if self.applied:
                with self.db.get_session() as session:
                    session.query(LipV2LineItemSolution).filter(
                        LipV2LineItemSolution.lookup_hash.in_(self.backup["hashes"])).delete(synchronize_session=False)
                    session.query(LipV2NonUnspscRule).filter(
                        LipV2NonUnspscRule.rule_order.in_(self.backup["rule_orders"])).delete(synchronize_session=False)
                    session.flush()
                    session.add_all(LipV2LineItemSolution(**row) for row in self.backup["solutions"])
                    session.add_all(LipV2NonUnspscRule(**row) for row in self.backup["rules"])
                    session.commit()
                self.applied = False
                (self.run.output / "database-restored.json").write_text(json.dumps({"restored": True}))
        finally:
            if self.lock is not None:
                try:
                    if self.lock_owned:
                        self.lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_ID})
                        self.lock.commit()
                finally:
                    self.lock.close()
                    self.lock = None
            if self.db is not None:
                self.db.close()


def restore_backup(path):
    """Recover the saved rows after an interrupted process using its database-backup.json."""
    from pathlib import Path
    from types import SimpleNamespace
    backup_path = Path(path)
    if (backup_path.parent / "database-restored.json").exists():
        raise ValueError("This backup has already been restored")
    preparation = DataPreparation(SimpleNamespace(output=backup_path.parent))
    preparation.backup = json.loads(backup_path.read_text())
    for key in ("solutions", "rules"):
        for row in preparation.backup[key]:
            row["id"] = UUID(row["id"])
            for column in ("created_at", "updated_at", "first_solved_at", "last_solved_at"):
                if row.get(column):
                    row[column] = datetime.fromisoformat(row[column])
            if "solved_for" in row:
                row["solved_for"] = [UUID(org) for org in row["solved_for"]]
    preparation.db = Database()
    if preparation.backup["database"] != preparation.database_identity():
        preparation.db.close()
        raise ValueError("The configured database differs from the backup's database")
    preparation.lock = preparation.db.engine.connect()
    acquired = preparation.lock.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_ID}).scalar()
    preparation.lock_owned = acquired
    if not acquired:
        preparation.restore()
        raise RuntimeError("Cannot recover data while a QA scenario is using it")
    preparation.lock.commit()
    preparation.applied = True
    preparation.restore()
