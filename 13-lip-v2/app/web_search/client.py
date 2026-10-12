from __future__ import annotations

import json
from typing import Protocol
from urllib import request

from ..core.config import Config
from .models import WebSearchRequest, WebSearchResult


class WebSearchClient(Protocol):
    def run(self, request: WebSearchRequest) -> WebSearchResult:
        ...


class SerperWebSearchClient:
    def __init__(self):
        self.api_key = Config.get_serper_api_key()
        self.base_url = Config.get_serper_base_url()

    def run(self, request_payload: WebSearchRequest) -> WebSearchResult:
        if not self.api_key:
            raise ValueError("SERPER_API_KEY is required for Serper web search")
        payload = {"q": request_payload.query}
        req = request.Request(
            url=self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req) as resp:  # noqa: S310
            body = json.loads(resp.read().decode("utf-8"))
        snippets = []
        organic = body.get("organic", []) or []
        for item in organic[:5]:
            snippet = str(item.get("snippet") or "").strip()
            if snippet:
                snippets.append(snippet)
        answer_box = body.get("answerBox") or {}
        answer = str(answer_box.get("snippet") or answer_box.get("answer") or "").strip()
        summary = answer or " ".join(snippets[:3])
        return WebSearchResult(
            query=request_payload.query,
            summary=summary,
            snippets=snippets,
            metadata={"provider": "serper"},
        )
