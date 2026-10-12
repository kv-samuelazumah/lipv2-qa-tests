from __future__ import annotations

import base64
import json
from typing import Dict, List, Optional, Protocol
from urllib import request

from ..core.config import Config
from ..identify_search.models import QueryType, UnspscSearchQuery
from .models import RetrievedHit


class UnspscSearchBackend(Protocol):
    def exact_search(self, query: UnspscSearchQuery, limit: int) -> List[RetrievedHit]:
        ...

    def bm25_search(self, query: UnspscSearchQuery, limit: int) -> List[RetrievedHit]:
        ...

    def semantic_search(
        self,
        query: UnspscSearchQuery,
        vector: List[float],
        limit: int,
    ) -> List[RetrievedHit]:
        ...


class ElasticsearchUnspscSearchBackend:
    def __init__(self):
        self.base_url = Config.get_elasticsearch_base_url().rstrip("/")
        self.index_name = Config.get_elasticsearch_index_name()
        self.api_key = Config.get_elasticsearch_api_key()
        self.username = Config.get_elasticsearch_username()
        self.password = Config.get_elasticsearch_password()

    def exact_search(self, query: UnspscSearchQuery, limit: int) -> List[RetrievedHit]:
        body = {
            "size": limit,
            "query": {
                "bool": {
                    "should": [
                        {"term": {"commodity_code.keyword": query.query}},
                        {"term": {"class_code.keyword": query.query}},
                        {"term": {"family_code.keyword": query.query}},
                        {"term": {"segment_code.keyword": query.query}},
                        {"term": {"commodity_title.keyword": query.query}},
                        {"term": {"class_title.keyword": query.query}},
                        {"term": {"family_title.keyword": query.query}},
                        {"term": {"segment_title.keyword": query.query}},
                        {"term": {"synonyms.keyword": query.query}},
                        {"term": {"examples.keyword": query.query}},
                    ],
                    "minimum_should_match": 1,
                }
            },
        }
        return self._search(body, query, "exact")

    def bm25_search(self, query: UnspscSearchQuery, limit: int) -> List[RetrievedHit]:
        body = {
            "size": limit,
            "query": {
                "multi_match": {
                    "query": query.query,
                    "fields": [
                        "search_document^4",
                        "commodity_title^4",
                        "class_title^3",
                        "family_title^2",
                        "segment_title^2",
                        "synonyms^3",
                        "examples",
                    ],
                    "type": "best_fields",
                }
            },
        }
        return self._search(body, query, "lexical")

    def semantic_search(
        self,
        query: UnspscSearchQuery,
        vector: List[float],
        limit: int,
    ) -> List[RetrievedHit]:
        body = {
            "size": limit,
            "knn": {
                "field": "embedding",
                "query_vector": vector,
                "k": limit,
                "num_candidates": max(limit * 4, 20),
            },
        }
        return self._search(body, query, "semantic")

    def _search(self, body: Dict, query: UnspscSearchQuery, channel: str) -> List[RetrievedHit]:
        url = f"{self.base_url}/{self.index_name}/_search"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"ApiKey {self.api_key}"
        elif self.username and self.password:
            token = base64.b64encode(f"{self.username}:{self.password}".encode("utf-8")).decode("utf-8")
            headers["Authorization"] = f"Basic {token}"

        req = request.Request(
            url=url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with request.urlopen(req) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))
        return [
            _map_hit(hit, query, channel)
            for hit in payload.get("hits", {}).get("hits", [])
        ]


def _map_hit(hit: Dict, query: UnspscSearchQuery, channel: str) -> RetrievedHit:
    source = hit.get("_source", {})
    title = (
        source.get("commodity_title")
        or source.get("class_title")
        or source.get("family_title")
        or source.get("segment_title")
        or ""
    )
    code = (
        source.get("commodity_code")
        or source.get("class_code")
        or source.get("family_code")
        or source.get("segment_code")
        or ""
    )
    return RetrievedHit(
        unspsc_code=str(code),
        level=str(source.get("level") or ""),
        title=str(title),
        path=str(source.get("path") or ""),
        source_channel=channel,
        source_query=query.query,
        source_query_type=query.query_type,
        source_priority=query.priority,
        raw_score=float(hit.get("_score") or 0.0),
        metadata={
            "index": hit.get("_index"),
            "id": hit.get("_id"),
            "segment_code": source.get("segment_code"),
            "segment_title": source.get("segment_title"),
            "family_code": source.get("family_code"),
            "family_title": source.get("family_title"),
            "class_code": source.get("class_code"),
            "class_title": source.get("class_title"),
            "commodity_code": source.get("commodity_code"),
            "commodity_title": source.get("commodity_title"),
            "code_description": source.get("code_description"),
            "aliases": source.get("code_aliases"),
            "synonyms": source.get("synonyms"),
            "specific_rules": source.get("specific_rules"),
        },
    )
