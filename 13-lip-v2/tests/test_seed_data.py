import sys
import unittest
from pathlib import Path


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.persistence.seeds.non_unspsc_rules import NON_UNSPSC_RULE_SEEDS


class SeedDataTests(unittest.TestCase):
    def test_rule_orders_are_unique(self):
        orders = [row["rule_order"] for row in NON_UNSPSC_RULE_SEEDS]
        self.assertEqual(len(orders), len(set(orders)))

    def test_seed_ids_are_unique(self):
        ids = [row["id"] for row in NON_UNSPSC_RULE_SEEDS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_seed_rows_have_required_keys(self):
        required = {
            "id",
            "rule_order",
            "label",
            "pattern",
            "policy_code",
            "status_code",
            "fallback_unspsc_code",
            "fallback_unspsc_level",
        }
        for row in NON_UNSPSC_RULE_SEEDS:
            self.assertTrue(required.issubset(row.keys()))


if __name__ == "__main__":
    unittest.main()
