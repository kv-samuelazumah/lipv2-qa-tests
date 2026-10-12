from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from .orm_models import LipV2LineItemSolution, LipV2NonUnspscRule
from .seeds.non_unspsc_rules import NON_UNSPSC_RULE_SEEDS
from .seeds.stable_lookups import STABLE_LOOKUP_SEEDS
from .seeds.unstable_lookups import UNSTABLE_LOOKUP_SEEDS


class _LineItemLookupSeeder:
    def __init__(self, session: Session, seeds: list[dict]):
        self.session = session
        self.seeds = seeds

    def seed(self) -> int:
        count = 0
        for seed in self.seeds:
            existing = (
                self.session.query(LipV2LineItemSolution)
                .filter(LipV2LineItemSolution.lookup_hash == seed["lookup_hash"])
                .one_or_none()
            )
            if existing is not None:
                continue
            values = dict(seed)
            values["id"] = UUID(seed["id"])
            values["solved_for"] = [UUID(org_id) for org_id in seed["solved_for"]]
            values["stable"] = len(set(values["solved_for"])) >= 3
            self.session.add(LipV2LineItemSolution(**values))
            count += 1
        self.session.commit()
        return count


class StableLookupSeeder(_LineItemLookupSeeder):
    def __init__(self, session: Session):
        super().__init__(session, STABLE_LOOKUP_SEEDS)


class UnstableLookupSeeder(_LineItemLookupSeeder):
    def __init__(self, session: Session):
        super().__init__(session, UNSTABLE_LOOKUP_SEEDS)


class NonUnspscRuleSeeder:
    def __init__(self, session: Session):
        self.session = session

    def seed(self) -> int:
        count = 0
        for seed in NON_UNSPSC_RULE_SEEDS:
            row = (
                self.session.query(LipV2NonUnspscRule)
                .filter(LipV2NonUnspscRule.rule_order == seed["rule_order"])
                .one_or_none()
            )
            if row is None:
                row = LipV2NonUnspscRule(
                    id=UUID(seed["id"]),
                    rule_order=seed["rule_order"],
                )
                self.session.add(row)
            row.label = seed["label"]
            row.pattern = seed["pattern"]
            row.policy_code = seed["policy_code"]
            row.status_code = seed["status_code"]
            row.fallback_unspsc_code = seed["fallback_unspsc_code"]
            row.fallback_unspsc_level = seed["fallback_unspsc_level"]
            row.active = True
            row.notes = seed.get("notes")
            count += 1
        self.session.commit()
        return count
