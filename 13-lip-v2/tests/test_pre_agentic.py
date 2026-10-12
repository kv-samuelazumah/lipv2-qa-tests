import sys
import unittest
from pathlib import Path


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.pre_agentic.models import LineItemSolution, NonUnspscRule, PreAgenticRequest, ResolvedBy
from app.pre_agentic.normalize import build_lookup_hash, normalize_line_item, normalize_supplier
from app.pre_agentic.loop import PreAgenticLoop
from app.persistence.repository import InMemoryLineItemSolutionRepository, InMemoryNonUnspscRuleRepository


class PreAgenticLoopTests(unittest.TestCase):
    def make_lookup_hash(self, supplier: str, line_item: str) -> str:
        return build_lookup_hash(
            normalize_supplier(supplier),
            normalize_line_item(line_item),
        )

    def test_unstable_lookup_wins_before_stable_and_rules(self):
        supplier = "Acme Ltd"
        line_item = "VAT"
        lookup_hash = self.make_lookup_hash(supplier, line_item)

        unstable = LineItemSolution(
            id="unstable-1",
            lookup_hash=lookup_hash,
            supplier_raw=supplier,
            supplier_normalized=normalize_supplier(supplier),
            line_item_raw=line_item,
            line_item_normalized=normalize_line_item(line_item),
            solved_for=["org-1"],
            stable=False,
            unspsc_code="44103103",
            unspsc_level="COMMODITY",
            source_type="MANUAL",
        )
        stable = LineItemSolution(
            id="stable-1",
            lookup_hash=lookup_hash,
            supplier_raw=supplier,
            supplier_normalized=normalize_supplier(supplier),
            line_item_raw=line_item,
            line_item_normalized=normalize_line_item(line_item),
            solved_for=["org-2", "org-3", "org-4"],
            stable=True,
            unspsc_code="99999999",
            unspsc_level="SEGMENT",
            source_type="PROMOTED",
        )
        rule = NonUnspscRule(
            id="rule-1",
            rule_order=1,
            label="VAT",
            pattern=r"\bvat\b",
            policy_code="exclude_from_spend",
            status_code="EXCLUDED",
            fallback_unspsc_code="1000",
            fallback_unspsc_level="SEGMENT",
        )

        loop = PreAgenticLoop(
            solution_repo=InMemoryLineItemSolutionRepository([unstable, stable]),
            rule_repo=InMemoryNonUnspscRuleRepository([rule]),
        )

        result = loop.run(PreAgenticRequest(org_id="org-1", supplier_raw=supplier, line_item_raw=line_item))

        self.assertIsNotNone(result)
        self.assertEqual(result.resolved_by, ResolvedBy.UNSTABLE_LOOKUP)
        self.assertEqual(result.unspsc_code, "44103103")

    def test_stable_lookup_wins_when_no_org_specific_hit_exists(self):
        supplier = "Acme Ltd"
        line_item = "Fuel"
        lookup_hash = self.make_lookup_hash(supplier, line_item)

        stable = LineItemSolution(
            id="stable-1",
            lookup_hash=lookup_hash,
            supplier_raw=supplier,
            supplier_normalized=normalize_supplier(supplier),
            line_item_raw=line_item,
            line_item_normalized=normalize_line_item(line_item),
            solved_for=["org-2", "org-3", "org-4"],
            stable=False,
            unspsc_code="15101505",
            unspsc_level="COMMODITY",
            source_type="PROMOTED",
        )

        loop = PreAgenticLoop(
            solution_repo=InMemoryLineItemSolutionRepository([stable]),
            rule_repo=InMemoryNonUnspscRuleRepository([]),
        )

        result = loop.run(PreAgenticRequest(org_id="org-1", supplier_raw=supplier, line_item_raw=line_item))

        self.assertIsNotNone(result)
        self.assertEqual(result.resolved_by, ResolvedBy.STABLE_LOOKUP)
        self.assertEqual(result.unspsc_code, "15101505")
        self.assertTrue(result.reasoning["stable"])

    def test_non_unspsc_rule_runs_after_both_solution_lookups(self):
        loop = PreAgenticLoop(
            solution_repo=InMemoryLineItemSolutionRepository([]),
            rule_repo=InMemoryNonUnspscRuleRepository(
                [
                    NonUnspscRule(
                        id="rule-1",
                        rule_order=2,
                        label="Late payment",
                        pattern=r"\blate payment\b",
                        policy_code="exclude_from_classification",
                        status_code="REVIEW_REQUIRED",
                        fallback_unspsc_code="4200",
                        fallback_unspsc_level="SEGMENT",
                    )
                ]
            ),
        )

        result = loop.run(
            PreAgenticRequest(
                org_id="org-1",
                supplier_raw="Acme Ltd",
                line_item_raw="Late payment interest",
            )
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.resolved_by, ResolvedBy.NON_UNSPSC_RULE)
        self.assertEqual(result.policy_code, "exclude_from_classification")
        self.assertEqual(result.status_code, "REVIEW_REQUIRED")

    def test_no_hit_returns_none(self):
        loop = PreAgenticLoop(
            solution_repo=InMemoryLineItemSolutionRepository([]),
            rule_repo=InMemoryNonUnspscRuleRepository([]),
        )

        result = loop.run(
            PreAgenticRequest(
                org_id="org-1",
                supplier_raw="Acme Ltd",
                line_item_raw="Industrial solvent",
            )
        )

        self.assertIsNone(result)

    def test_stable_is_derived_from_solved_for_count(self):
        row = LineItemSolution(
            id="row-1",
            lookup_hash="hash",
            supplier_raw="Acme",
            supplier_normalized="acme",
            line_item_raw="fuel",
            line_item_normalized="fuel",
            solved_for=["org-1", "org-2", "org-3"],
            stable=False,
        )

        recomputed = row.recompute_stable()

        self.assertTrue(recomputed.stable)


if __name__ == "__main__":
    unittest.main()
