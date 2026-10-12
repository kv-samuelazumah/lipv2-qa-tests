from __future__ import annotations

import json
from typing import Any, Protocol

from ..core.config import Config
from .models import IdentifySearchRequest, IdentifySearchResponse
from .prompt import (
    IDENTIFY_SEARCH_SYSTEM_PROMPT,
    build_identify_search_user_prompt,
)


class IdentifySearchClient(Protocol):
    def run(self, request: IdentifySearchRequest) -> IdentifySearchResponse:
        ...


class DeepSeekIdentifySearchClient:
    def __init__(self):
        self.model = Config.get_identify_search_model()
        self.api_key = Config.get_identify_search_api_key()
        self.base_url = Config.get_identify_search_base_url()
        self._client: Any = None

    def run(self, request: IdentifySearchRequest) -> IdentifySearchResponse:
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY is required for Identify-and-Search calls")

        try:
            from openai import OpenAI
        except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency
            raise RuntimeError("openai package is required for DeepSeekIdentifySearchClient") from exc

        if self._client is None:
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        response = self._client.chat.completions.create(
            model=self.model,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": IDENTIFY_SEARCH_SYSTEM_PROMPT},
                {"role": "user", "content": build_identify_search_user_prompt(request)},
            ],
        )
        content = response.choices[0].message.content or "{}"
        parsed = IdentifySearchResponse.from_dict(json.loads(content))
        return parsed.validate_against_request(request)
