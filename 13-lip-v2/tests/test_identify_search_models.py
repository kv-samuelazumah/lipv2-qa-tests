import sys
import unittest
from pathlib import Path


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.identify_search.models import (
    ContextDependency,
    IdentifySearchRequest,
    IdentifySearchResponse,
    ItemNature,
    QueryType,
    UnderstandingConfidence,
    WarningCategory,
)


def make_request(web_search_allowed: bool = True, max_queries: int = 3) -> IdentifySearchRequest:
    return IdentifySearchRequest.from_dict(
        {
            "global_config": {
                "max_unspsc_search_queries": max_queries,
                "web_search_allowed": web_search_allowed,
            },
            "target_line": {
                "item_raw_row": "Notebook",
                "description_clean": "notebook",
                "unit_of_measure_raw": "ea",
                "quantity": {"value": 1},
                "unit_price": {"value": 1200},
                "line_subtotal": {"value": 1200},
            },
            "invoice_context": {
                "supplier_name": "Acme Ltd",
                "unspsc_ready_invoice_description": "Office equipment and supplies",
                "supplier_sic_label": "Office supplies retail",
                "buyer_sic_label": None,
            },
            "house_rules": [],
        }
    )


def make_response(queries: list[dict], web_search_candidate: bool = False, suggested_web_query=None):
    return IdentifySearchResponse.from_dict(
        {
            "item_hypothesis": {
                "understanding_confidence": UnderstandingConfidence.MEDIUM.value,
                "item_nature": ItemNature.PHYSICAL_GOOD.value,
                "primary_identity": "laptop computer",
                "identity_explanation": "High unit price points to computer hardware instead of paper stationery.",
                "interpretation": {
                    "what_it_is": "Likely a laptop or notebook computer.",
                    "what_it_is_not": ["paper notebook"],
                    "ambiguity": [],
                },
            },
            "evidence_usage": {
                "target_line_fields_used": [
                    "item_raw_row",
                    "description_clean",
                    "unit_price",
                ],
                "other_evidence_used": [
                    {
                        "evidence_type": "supplier_name",
                        "evidence_text": "Acme Ltd",
                        "used_for": "Weak prior only.",
                    }
                ],
                "context_dependency": ContextDependency.LOW.value,
            },
            "candidate_evaluation_warnings": [
                {
                    "warning_category": WarningCategory.PRICE_DISAMBIGUATION.value,
                    "warning": "Avoid stationery notebook candidates.",
                }
            ],
            "web_search_signal": {
                "web_search_candidate": web_search_candidate,
                "suggested_web_query": suggested_web_query,
            },
            "unspsc_search_queries": queries,
        }
    )


class IdentifySearchModelTests(unittest.TestCase):
    def test_response_validates_against_request(self):
        request = make_request()
        response = make_response(
            [
                {
                    "query": "laptop computer",
                    "query_type": QueryType.SPECIFIC.value,
                    "priority": 1,
                    "reason": "Primary item identity.",
                },
                {
                    "query": "office computing equipment",
                    "query_type": QueryType.CONTEXTUAL.value,
                    "priority": 2,
                    "reason": "Invoice context supports office equipment.",
                },
                {
                    "query": "computer equipment",
                    "query_type": QueryType.BROAD.value,
                    "priority": 3,
                    "reason": "Broad fallback query.",
                },
            ]
        )

        validated = response.validate_against_request(request)

        self.assertEqual(len(validated.unspsc_search_queries), 3)

    def test_response_rejects_too_many_queries(self):
        request = make_request(max_queries=2)
        response = make_response(
            [
                {
                    "query": "q1",
                    "query_type": QueryType.SPECIFIC.value,
                    "priority": 1,
                    "reason": "a",
                },
                {
                    "query": "q2",
                    "query_type": QueryType.CONTEXTUAL.value,
                    "priority": 2,
                    "reason": "b",
                },
                {
                    "query": "q3",
                    "query_type": QueryType.BROAD.value,
                    "priority": 3,
                    "reason": "c",
                },
            ]
        )

        with self.assertRaises(ValueError):
            response.validate_against_request(request)

    def test_response_rejects_web_search_when_disallowed(self):
        request = make_request(web_search_allowed=False)
        response = make_response(
            [
                {
                    "query": "computer equipment",
                    "query_type": QueryType.BROAD.value,
                    "priority": 1,
                    "reason": "fallback",
                }
            ],
            web_search_candidate=True,
            suggested_web_query="site:example.com notebook",
        )

        with self.assertRaises(ValueError):
            response.validate_against_request(request)

    def test_response_requires_broad_query(self):
        request = make_request()
        response = make_response(
            [
                {
                    "query": "laptop computer",
                    "query_type": QueryType.SPECIFIC.value,
                    "priority": 1,
                    "reason": "primary",
                }
            ]
        )

        with self.assertRaises(ValueError):
            response.validate_against_request(request)


if __name__ == "__main__":
    unittest.main()
