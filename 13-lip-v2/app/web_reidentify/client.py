from __future__ import annotations

import json
from typing import Protocol

from ..core.config import Config
from ..identify_search.models import IdentifySearchResponse
from .models import WebReidentifyRequest
from .prompt import WEB_REIDENTIFY_SYSTEM_PROMPT, build_web_reidentify_user_prompt


class WebReidentifyClient(Protocol):
    def run(self, request: WebReidentifyRequest) -> IdentifySearchResponse:
        ...


class DeepSeekWebReidentifyClient:
    def __init__(self):
        self.model = Config.get_web_reidentify_model()
        self.api_key = Config.get_web_reidentify_api_key()
        self.base_url = Config.get_web_reidentify_base_url()

    def run(self, request: WebReidentifyRequest) -> IdentifySearchResponse:
        if not self.api_key:
            raise ValueError("WEB_REIDENTIFY_API_KEY or DEEPSEEK_API_KEY is required for web re-identify calls")

        try:
            from openai import OpenAI
        except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency
            raise RuntimeError("openai package is required for DeepSeekWebReidentifyClient") from exc

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        response = client.chat.completions.create(
            model=self.model,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": WEB_REIDENTIFY_SYSTEM_PROMPT},
                {"role": "user", "content": build_web_reidentify_user_prompt(request)},
            ],
        )
        content = response.choices[0].message.content or "{}"
        parsed = IdentifySearchResponse.from_dict(json.loads(content))
        return parsed.validate_against_request(request.identify_search_input)
