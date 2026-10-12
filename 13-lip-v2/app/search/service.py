from __future__ import annotations

from typing import List, Optional

from ..core.config import Config
from .embedding_client import EmbeddingClient, OpenAIEmbeddingClient
from .elasticsearch_client import ElasticsearchUnspscSearchBackend, UnspscSearchBackend
from .fusion import fuse_query_hits, stratified_union
from .models import QueryCandidatePool, UnspscSearchOutput, UnspscSearchToolRequest, build_unspsc_search_output


class UnspscSearchTool:
    def __init__(
        self,
        search_backend: Optional[UnspscSearchBackend] = None,
        embedding_client: Optional[EmbeddingClient] = None,
    ):
        self.search_backend = search_backend or ElasticsearchUnspscSearchBackend()
        self.embedding_client = embedding_client or OpenAIEmbeddingClient()

    def run(self, request: UnspscSearchToolRequest) -> UnspscSearchOutput:
        per_query_pools: List[QueryCandidatePool] = []
        ordered_queries = sorted(request.queries, key=lambda value: value.priority)
        semantic_vectors = self.embedding_client.embed_texts(
            [query.query for query in ordered_queries]
        )
        if len(semantic_vectors) != len(ordered_queries):
            raise ValueError(
                "Embedding provider returned a different number of vectors than requested"
            )

        for query, semantic_vector in zip(ordered_queries, semantic_vectors):
            exact_hits = self.search_backend.exact_search(query, request.max_candidates_per_query)
            lexical_hits = self.search_backend.bm25_search(query, request.max_candidates_per_query)
            semantic_hits = self.search_backend.semantic_search(
                query,
                semantic_vector,
                request.max_candidates_per_query,
            )
            per_query_pools.append(
                fuse_query_hits(
                    query=query.query,
                    query_type=query.query_type,
                    priority=query.priority,
                    exact_hits=exact_hits,
                    lexical_hits=lexical_hits,
                    semantic_hits=semantic_hits,
                    limit=request.max_candidates_per_query,
                )
            )
        grouped_candidates = stratified_union(per_query_pools, request.max_candidates_total)
        return build_unspsc_search_output(
            unspsc_version=Config.get_unspsc_version(),
            queries=request.queries,
            grouped_candidates=grouped_candidates,
            max_candidates_per_query=request.max_candidates_per_query,
            max_candidates_total=request.max_candidates_total,
        )
