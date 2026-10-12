import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.persistence import repository as repo_module


class FakeColumn:
    def __eq__(self, other):
        return self

    def is_(self, other):
        return self

    def asc(self):
        return self


class FakeSolutionModel:
    lookup_hash = FakeColumn()
    stable = FakeColumn()
    updated_at = FakeColumn()


class FakeRuleModel:
    active = FakeColumn()
    rule_order = FakeColumn()


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return list(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None


class FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.committed = False

    def query(self, model):
        return FakeQuery(self.rows)

    def add(self, row):
        if row not in self.rows:
            self.rows.append(row)

    def commit(self):
        self.committed = True

    def refresh(self, row):
        return None


class PostgresRepositoryTests(unittest.TestCase):
    def test_find_unstable_returns_org_specific_match(self):
        row = SimpleNamespace(
            id="row-1",
            lookup_hash="hash-1",
            supplier_raw="Acme Ltd",
            supplier_normalized="acme ltd",
            line_item_raw="VAT",
            line_item_normalized="vat",
            solved_for=[
                repo_module.UUID("11111111-1111-1111-1111-111111111111"),
            ],
            stable=False,
            unspsc_code="44103103",
            unspsc_level="COMMODITY",
            policy_code=None,
            status_code="SOLVED",
            source_type="MANUAL",
            reasoning={},
            updated_at=None,
        )
        session = FakeSession([row])

        with patch.object(repo_module, "SQLALCHEMY_AVAILABLE", True), patch.object(
            repo_module, "LipV2LineItemSolution", FakeSolutionModel
        ), patch.object(repo_module, "desc", lambda value: value):
            repository = repo_module.PostgresLineItemSolutionRepository(session)
            result = repository.find_unstable(
                lookup_hash="hash-1",
                org_id="11111111-1111-1111-1111-111111111111",
            )

        self.assertIsNotNone(result)
        self.assertEqual(result.id, "row-1")
        self.assertFalse(result.stable)

    def test_find_stable_returns_latest_stable_match(self):
        row = SimpleNamespace(
            id="row-2",
            lookup_hash="hash-2",
            supplier_raw="Acme Ltd",
            supplier_normalized="acme ltd",
            line_item_raw="Fuel",
            line_item_normalized="fuel",
            solved_for=[
                repo_module.UUID("11111111-1111-1111-1111-111111111111"),
                repo_module.UUID("22222222-2222-2222-2222-222222222222"),
                repo_module.UUID("33333333-3333-3333-3333-333333333333"),
            ],
            stable=True,
            unspsc_code="15101505",
            unspsc_level="COMMODITY",
            policy_code=None,
            status_code="SOLVED",
            source_type="PROMOTED",
            reasoning={},
            updated_at=None,
        )
        session = FakeSession([row])

        with patch.object(repo_module, "SQLALCHEMY_AVAILABLE", True), patch.object(
            repo_module, "LipV2LineItemSolution", FakeSolutionModel
        ), patch.object(repo_module, "desc", lambda value: value):
            repository = repo_module.PostgresLineItemSolutionRepository(session)
            result = repository.find_stable(lookup_hash="hash-2")

        self.assertIsNotNone(result)
        self.assertTrue(result.stable)
        self.assertEqual(result.unspsc_code, "15101505")

    def test_find_first_match_uses_rule_ordered_rows(self):
        row = SimpleNamespace(
            id="rule-1",
            rule_order=1,
            label="VAT",
            pattern=r"\bvat\b",
            policy_code="exclude_from_spend",
            status_code="EXCLUDED",
            fallback_unspsc_code="1000",
            fallback_unspsc_level="SEGMENT",
            active=True,
        )
        session = FakeSession([row])

        with patch.object(repo_module, "SQLALCHEMY_AVAILABLE", True), patch.object(
            repo_module, "LipV2NonUnspscRule", FakeRuleModel
        ):
            repository = repo_module.PostgresNonUnspscRuleRepository(session)
            result = repository.find_first_match("VAT")

        self.assertIsNotNone(result)
        self.assertEqual(result.label, "VAT")
        self.assertEqual(result.policy_code, "exclude_from_spend")

    def test_upsert_agentic_solution_appends_org_and_promotes_stable(self):
        row = SimpleNamespace(
            id="row-3",
            lookup_hash="existing-hash",
            supplier_raw="Acme Ltd",
            supplier_normalized="acme ltd",
            line_item_raw="Notebook",
            line_item_normalized="notebook",
            solved_for=[
                repo_module.UUID("11111111-1111-1111-1111-111111111111"),
                repo_module.UUID("22222222-2222-2222-2222-222222222222"),
            ],
            stable=False,
            unspsc_code="43211503",
            unspsc_level="COMMODITY",
            policy_code=None,
            status_code="SOLVED",
            source_type="AGENTIC_MATCH",
            reasoning={},
            updated_at=None,
        )
        session = FakeSession([row])

        with patch.object(repo_module, "SQLALCHEMY_AVAILABLE", True), patch.object(
            repo_module, "LipV2LineItemSolution", FakeSolutionModel
        ), patch.object(repo_module, "desc", lambda value: value):
            repository = repo_module.PostgresLineItemSolutionRepository(session)
            with patch.object(repo_module, "build_lookup_hash", return_value="existing-hash"):
                result = repository.upsert_agentic_solution(
                    org_id="33333333-3333-3333-3333-333333333333",
                    supplier_raw="Acme Ltd",
                    line_item_raw="Notebook",
                    unspsc_code="43211503",
                    unspsc_level="COMMODITY",
                    reasoning={"selection_reason": "test"},
                    selected_label="Laptop computers",
                )

        self.assertTrue(session.committed)
        self.assertTrue(result.stable)
        self.assertEqual(len(result.solved_for), 3)
        self.assertEqual(result.reasoning["selected_label"], "Laptop computers")

    def test_upsert_agentic_solution_resets_consensus_on_conflicting_code(self):
        row = SimpleNamespace(
            id="row-4",
            lookup_hash="existing-hash",
            supplier_raw="Acme Ltd",
            supplier_normalized="acme ltd",
            line_item_raw="Notebook",
            line_item_normalized="notebook",
            solved_for=[
                repo_module.UUID("11111111-1111-1111-1111-111111111111"),
                repo_module.UUID("22222222-2222-2222-2222-222222222222"),
                repo_module.UUID("33333333-3333-3333-3333-333333333333"),
            ],
            stable=True,
            unspsc_code="12345678",
            unspsc_level="COMMODITY",
            policy_code=None,
            status_code="SOLVED",
            source_type="AGENTIC_MATCH",
            reasoning={},
            updated_at=None,
        )
        session = FakeSession([row])

        with patch.object(repo_module, "SQLALCHEMY_AVAILABLE", True), patch.object(
            repo_module, "LipV2LineItemSolution", FakeSolutionModel
        ), patch.object(repo_module, "desc", lambda value: value):
            repository = repo_module.PostgresLineItemSolutionRepository(session)
            with patch.object(repo_module, "build_lookup_hash", return_value="existing-hash"):
                result = repository.upsert_agentic_solution(
                    org_id="44444444-4444-4444-4444-444444444444",
                    supplier_raw="Acme Ltd",
                    line_item_raw="Notebook",
                    unspsc_code="43211503",
                    unspsc_level="COMMODITY",
                    reasoning={"selection_reason": "test"},
                )

        self.assertEqual(result.solved_for, ["44444444-4444-4444-4444-444444444444"])
        self.assertFalse(result.stable)
        self.assertEqual(result.unspsc_code, "43211503")


if __name__ == "__main__":
    unittest.main()
