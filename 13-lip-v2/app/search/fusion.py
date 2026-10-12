from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from ..identify_search.models import QueryType
from .models import FusedCandidate, QueryCandidatePool, RetrievedHit, StratifiedCandidatePools


RRF_K = 60


def fuse_query_hits(
    query: str,
    query_type: QueryType,
    priority: int,
    exact_hits: List[RetrievedHit],
    lexical_hits: List[RetrievedHit],
    semantic_hits: List[RetrievedHit],
    limit: int,
) -> QueryCandidatePool:
    grouped: Dict[str, dict] = {}
    ranked_channels = {
        "exact": exact_hits,
        "lexical": lexical_hits,
        "semantic": semantic_hits,
    }

    for channel, hits in ranked_channels.items():
        for idx, hit in enumerate(hits, start=1):
            current = grouped.setdefault(
                hit.unspsc_code,
                {
                    "unspsc_code": hit.unspsc_code,
                    "level": hit.level,
                    "title": hit.title,
                    "path": hit.path,
                    "source_query": query,
                    "source_query_type": query_type,
                    "source_priority": priority,
                    "rrf_score": 0.0,
                    "best_exact_rank": None,
                    "best_lexical_rank": None,
                    "best_semantic_rank": None,
                    "channels_present": [],
                    "metadata": dict(hit.metadata),
                },
            )
            current["rrf_score"] += 1.0 / (RRF_K + idx)
            rank_field = {
                "exact": "best_exact_rank",
                "lexical": "best_lexical_rank",
                "semantic": "best_semantic_rank",
            }[channel]
            previous_rank = current[rank_field]
            current[rank_field] = idx if previous_rank is None else min(previous_rank, idx)
            if channel not in current["channels_present"]:
                current["channels_present"].append(channel)

    candidates = [
        FusedCandidate(
            unspsc_code=value["unspsc_code"],
            level=value["level"],
            title=value["title"],
            path=value["path"],
            source_query=value["source_query"],
            source_query_type=value["source_query_type"],
            source_priority=value["source_priority"],
            rrf_score=value["rrf_score"],
            best_exact_rank=value["best_exact_rank"],
            best_lexical_rank=value["best_lexical_rank"],
            best_semantic_rank=value["best_semantic_rank"],
            channels_present=sorted(value["channels_present"]),
            metadata=value["metadata"],
        )
        for value in grouped.values()
    ]
    candidates.sort(
        key=lambda value: (
            -value.rrf_score,
            value.best_exact_rank if value.best_exact_rank is not None else 10**9,
            value.best_lexical_rank if value.best_lexical_rank is not None else 10**9,
            value.best_semantic_rank if value.best_semantic_rank is not None else 10**9,
            value.unspsc_code,
        )
    )
    return QueryCandidatePool(
        query=query,
        query_type=query_type,
        priority=priority,
        candidates=candidates[:limit],
    )


def stratified_union(
    pools: List[QueryCandidatePool],
    max_candidates_total: int,
) -> StratifiedCandidatePools:
    grouped: Dict[QueryType, List[FusedCandidate]] = defaultdict(list)
    seen_codes: set[str] = set()

    for query_type in (QueryType.SPECIFIC, QueryType.BROAD, QueryType.CONTEXTUAL):
        same_type = sorted(
            [pool for pool in pools if pool.query_type == query_type],
            key=lambda pool: pool.priority,
        )
        max_depth = max((len(pool.candidates) for pool in same_type), default=0)
        for round_index in range(max_depth):
            for pool in same_type:
                if round_index >= len(pool.candidates):
                    continue
                candidate = pool.candidates[round_index]
                if candidate.unspsc_code in seen_codes:
                    continue
                grouped[query_type].append(candidate)
                seen_codes.add(candidate.unspsc_code)
                if total_candidates(grouped) >= max_candidates_total:
                    return StratifiedCandidatePools(
                        specific=grouped[QueryType.SPECIFIC],
                        broad=grouped[QueryType.BROAD],
                        contextual=grouped[QueryType.CONTEXTUAL],
                    )

    return StratifiedCandidatePools(
        specific=grouped[QueryType.SPECIFIC],
        broad=grouped[QueryType.BROAD],
        contextual=grouped[QueryType.CONTEXTUAL],
    )


def total_candidates(grouped: Dict[QueryType, List[FusedCandidate]]) -> int:
    return sum(len(values) for values in grouped.values())
