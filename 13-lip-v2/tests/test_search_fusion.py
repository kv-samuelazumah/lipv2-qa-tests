import sys
import unittest
from pathlib import Path


sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.identify_search.models import QueryType
from app.search.fusion import fuse_query_hits, stratified_union
from app.search.models import RetrievedHit


def hit(code: str, channel: str, query: str, query_type: QueryType, priority: int, score: float = 1.0):
    return RetrievedHit(
        unspsc_code=code,
        level="COMMODITY",
        title=f"title-{code}",
        path=f"path/{code}",
        source_channel=channel,
        source_query=query,
        source_query_type=query_type,
        source_priority=priority,
        raw_score=score,
    )


class SearchFusionTests(unittest.TestCase):
    def test_fuse_query_hits_groups_by_unspsc_and_scores_rrf(self):
        pool = fuse_query_hits(
            query="laptop computer",
            query_type=QueryType.SPECIFIC,
            priority=1,
            exact_hits=[
                hit("43211503", "exact", "laptop computer", QueryType.SPECIFIC, 1),
            ],
            lexical_hits=[
                hit("43211503", "lexical", "laptop computer", QueryType.SPECIFIC, 1),
                hit("43211509", "lexical", "laptop computer", QueryType.SPECIFIC, 1),
            ],
            semantic_hits=[
                hit("43211503", "semantic", "laptop computer", QueryType.SPECIFIC, 1),
            ],
            limit=10,
        )

        self.assertEqual(pool.candidates[0].unspsc_code, "43211503")
        self.assertGreater(pool.candidates[0].rrf_score, pool.candidates[1].rrf_score)
        self.assertEqual(pool.candidates[0].best_exact_rank, 1)
        self.assertEqual(pool.candidates[0].best_lexical_rank, 1)
        self.assertEqual(pool.candidates[0].best_semantic_rank, 1)

    def test_stratified_union_preserves_grouping_and_deduplicates(self):
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
            exact_hits=[hit("43211503", "exact", "computer equipment", QueryType.BROAD, 2)],
            lexical_hits=[hit("43211507", "lexical", "computer equipment", QueryType.BROAD, 2)],
            semantic_hits=[],
            limit=5,
        )
        contextual = fuse_query_hits(
            query="office computing equipment",
            query_type=QueryType.CONTEXTUAL,
            priority=3,
            exact_hits=[hit("44111500", "exact", "office computing equipment", QueryType.CONTEXTUAL, 3)],
            lexical_hits=[],
            semantic_hits=[],
            limit=5,
        )

        result = stratified_union([specific, broad, contextual], max_candidates_total=10)

        self.assertEqual([value.unspsc_code for value in result.specific], ["43211503"])
        self.assertEqual([value.unspsc_code for value in result.broad], ["43211507"])
        self.assertEqual([value.unspsc_code for value in result.contextual], ["44111500"])


if __name__ == "__main__":
    unittest.main()
