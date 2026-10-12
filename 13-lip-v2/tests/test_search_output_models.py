import sys
import unittest
from pathlib import Path


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.identify_search.models import QueryType, UnspscSearchQuery
from app.search.fusion import fuse_query_hits, stratified_union
from app.search.models import RetrievedHit, build_unspsc_search_output


def hit(code: str, channel: str, query: str, query_type: QueryType, priority: int, score: float = 1.0):
    return RetrievedHit(
        unspsc_code=code,
        level="commodity",
        title=f"title-{code}",
        path=f"path/{code}",
        source_channel=channel,
        source_query=query,
        source_query_type=query_type,
        source_priority=priority,
        raw_score=score,
        metadata={
            "segment_code": "43000000",
            "segment_title": "IT",
            "family_code": "43210000",
            "family_title": "Computer equipment",
            "class_code": "43211500",
            "class_title": "Computers",
            "commodity_code": code,
            "commodity_title": f"title-{code}",
            "code_description": "description",
            "synonyms": ["alias-a"],
        },
    )


class SearchOutputModelTests(unittest.TestCase):
    def test_build_unspsc_search_output_normalizes_candidates(self):
        specific = fuse_query_hits(
            query="laptop computer",
            query_type=QueryType.SPECIFIC,
            priority=1,
            exact_hits=[hit("43211503", "exact", "laptop computer", QueryType.SPECIFIC, 1)],
            lexical_hits=[],
            semantic_hits=[],
            limit=5,
        )
        broad = fuse_query_hits(
            query="computer equipment",
            query_type=QueryType.BROAD,
            priority=2,
            exact_hits=[],
            lexical_hits=[hit("43210000", "lexical", "computer equipment", QueryType.BROAD, 2)],
            semantic_hits=[],
            limit=5,
        )
        grouped = stratified_union([specific, broad], max_candidates_total=10)

        output = build_unspsc_search_output(
            unspsc_version="test-v1",
            queries=[
                UnspscSearchQuery(
                    query="laptop computer",
                    query_type=QueryType.SPECIFIC,
                    priority=1,
                    reason="primary",
                ),
                UnspscSearchQuery(
                    query="computer equipment",
                    query_type=QueryType.BROAD,
                    priority=2,
                    reason="fallback",
                ),
            ],
            grouped_candidates=grouped,
            max_candidates_per_query=5,
            max_candidates_total=10,
        )

        payload = output.as_dict()

        self.assertEqual(payload["retrieval_metadata"]["candidate_count"], 2)
        self.assertEqual(payload["candidates"][0]["code"], "43211503")
        self.assertEqual(payload["candidates"][0]["hierarchy_path"]["class"]["code"], "43211500")
        self.assertEqual(payload["candidates"][0]["matched_queries"][0]["query"], "laptop computer")


if __name__ == "__main__":
    unittest.main()
