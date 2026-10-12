import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.pre_agentic.service import PreAgenticService


class PreAgenticServiceTests(unittest.TestCase):
    def test_resolve_returns_serialized_result(self):
        fake_db = MagicMock()
        fake_session = MagicMock()
        fake_db.get_session.return_value = fake_session

        fake_result = {
            "resolved_by": "STABLE_LOOKUP",
            "status_code": "SOLVED",
            "policy_code": None,
            "unspsc_code": "15101505",
            "unspsc_level": "COMMODITY",
            "lookup_hash": "hash-1",
            "reasoning": {},
        }

        with patch("app.pre_agentic.service.PreAgenticLoop") as loop_cls, patch(
            "app.pre_agentic.service.PostgresLineItemSolutionRepository"
        ), patch("app.pre_agentic.service.PostgresNonUnspscRuleRepository"):
            loop = loop_cls.return_value
            loop.run.return_value = object()
            loop.serialize.return_value = fake_result

            service = PreAgenticService(fake_db)
            result = service.resolve(
                org_id="11111111-1111-1111-1111-111111111111",
                supplier_raw="Acme Ltd",
                line_item_raw="Fuel",
            )

        self.assertEqual(result, fake_result)
        fake_session.close.assert_called_once()

    def test_resolve_returns_none_when_no_match(self):
        fake_db = MagicMock()
        fake_session = MagicMock()
        fake_db.get_session.return_value = fake_session

        with patch("app.pre_agentic.service.PreAgenticLoop") as loop_cls, patch(
            "app.pre_agentic.service.PostgresLineItemSolutionRepository"
        ), patch("app.pre_agentic.service.PostgresNonUnspscRuleRepository"):
            loop = loop_cls.return_value
            loop.run.return_value = None

            service = PreAgenticService(fake_db)
            result = service.resolve(
                org_id="11111111-1111-1111-1111-111111111111",
                supplier_raw="Acme Ltd",
                line_item_raw="Unknown item",
            )

        self.assertIsNone(result)
        fake_session.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
