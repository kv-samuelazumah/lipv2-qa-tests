from __future__ import annotations

import json

from .models import WebReidentifyRequest


WEB_REIDENTIFY_SYSTEM_PROMPT = """
You are the dedicated web-assisted re-identification step in an agentic UNSPSC classification pipeline.

You are given:
1. the original Identify-and-Search input;
2. the previous Identify-and-Search output;
3. the Evaluate Candidates output that requested web search;
4. the system web-search results.

Your task is to produce a refreshed Identify-and-Search style output:
- grounded item hypothesis;
- evidence usage;
- candidate evaluation warnings;
- web-search signal;
- ordered UNSPSC search queries.

Return valid JSON only.
Do not output markdown.
Do not output explanations outside the JSON.
Do not select a UNSPSC code.
""".strip()


def build_web_reidentify_user_prompt(request: WebReidentifyRequest) -> str:
    return json.dumps(request.as_dict(), indent=2, sort_keys=True)
