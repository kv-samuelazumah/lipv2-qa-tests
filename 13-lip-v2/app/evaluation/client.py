from __future__ import annotations

import json
import logging
from typing import Any, Optional, Protocol

from ..core.config import Config
from .models import EvaluateCandidatesRequest, EvaluateCandidatesResponse, EvaluationDecision
from .prompt import EVALUATE_CANDIDATES_SYSTEM_PROMPT, build_evaluate_candidates_user_prompt

LOG = logging.getLogger("lip.v2.evaluation")

# Non-canonical decision values the model has been seen to (or plausibly
# could) return in json_object mode, mapped onto the enum.
_DECISION_ALIASES = {
    "select": EvaluationDecision.SELECT_CANDIDATE.value,
    "selected": EvaluationDecision.SELECT_CANDIDATE.value,
    "selection": EvaluationDecision.SELECT_CANDIDATE.value,
    "select_code": EvaluationDecision.SELECT_CANDIDATE.value,
    "selected_candidate": EvaluationDecision.SELECT_CANDIDATE.value,
    "classify": EvaluationDecision.SELECT_CANDIDATE.value,
    "classified": EvaluationDecision.SELECT_CANDIDATE.value,
    "re_search": EvaluationDecision.RE_SEARCH_UNSPSC.value,
    "research": EvaluationDecision.RE_SEARCH_UNSPSC.value,
    "research_unspsc": EvaluationDecision.RE_SEARCH_UNSPSC.value,
    "websearch": EvaluationDecision.WEB_SEARCH.value,
    "unable": EvaluationDecision.UNABLE_TO_RESOLVE.value,
    "unresolved": EvaluationDecision.UNABLE_TO_RESOLVE.value,
}


class EvaluateCandidatesClient(Protocol):
    def run(self, request: EvaluateCandidatesRequest) -> EvaluateCandidatesResponse:
        ...


class DeepSeekEvaluateCandidatesClient:
    def __init__(self):
        self.model = Config.get_evaluate_candidates_model()
        self.api_key = Config.get_evaluate_candidates_api_key()
        self.base_url = Config.get_evaluate_candidates_base_url()
        self._client: Any = None

    def run(self, request: EvaluateCandidatesRequest) -> EvaluateCandidatesResponse:
        if not self.api_key:
            raise ValueError("EVALUATE_CANDIDATES_API_KEY or DEEPSEEK_API_KEY is required for Evaluate Candidates calls")

        try:
            from openai import OpenAI
        except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency
            raise RuntimeError("openai package is required for DeepSeekEvaluateCandidatesClient") from exc

        if self._client is None:
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        response = self._client.chat.completions.create(
            model=self.model,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": EVALUATE_CANDIDATES_SYSTEM_PROMPT},
                {"role": "user", "content": build_evaluate_candidates_user_prompt(request)},
            ],
        )
        content = response.choices[0].message.content or "{}"
        raw_payload = json.loads(content)
        LOG.debug("Evaluate Candidates raw response: %s", content)
        payload = _normalize_evaluate_candidates_payload(raw_payload, request)
        if payload["decision"] != raw_payload.get("decision"):
            LOG.warning(
                "Evaluate Candidates decision repaired raw_decision=%r normalized_decision=%s raw_response=%s",
                raw_payload.get("decision"),
                payload["decision"],
                content,
            )
        parsed = EvaluateCandidatesResponse.from_dict(payload)
        return parsed.validate_against_request(request)


def _normalize_evaluate_candidates_payload(
    payload: dict[str, Any],
    request: EvaluateCandidatesRequest,
) -> dict[str, Any]:
    normalized = dict(payload)
    decision = _resolve_decision(normalized, request)
    normalized["decision"] = decision
    decision_reason = (
        normalized.get("decision_reason")
        or normalized.get("reasoning")
        or normalized.get("selection_reason")
        or normalized.get("reason")
        or ""
    )
    normalized["decision_reason"] = str(decision_reason).strip()
    normalized.setdefault("rule_ids_used", [])

    if "candidate_set_diagnosis" not in normalized:
        normalized["candidate_set_diagnosis"] = _default_candidate_set_diagnosis(str(decision or ""))

    if decision == "select_candidate" and normalized.get("final_classification") is None:
        selected_code = normalized.get("selected_code") or normalized.get("code")
        if selected_code:
            final_classification = _build_final_classification_from_selected_code(
                selected_code=str(selected_code),
                selected_label=normalized.get("selected_label") or normalized.get("label"),
                selection_reason=normalized["decision_reason"] or "Model selected candidate from returned UNSPSC set.",
                request=request,
            )
            if final_classification is not None:
                normalized["final_classification"] = final_classification

    normalized.setdefault("final_classification", None)
    normalized.setdefault("re_search_unspsc", None)
    normalized.setdefault("web_search", None)
    normalized.setdefault("unable_to_resolve", {} if decision == "unable_to_resolve" else None)

    allowed = {
        "decision",
        "decision_reason",
        "candidate_set_diagnosis",
        "final_classification",
        "re_search_unspsc",
        "web_search",
        "unable_to_resolve",
        "rule_ids_used",
    }
    return {key: value for key, value in normalized.items() if key in allowed}


def _resolve_decision(payload: dict[str, Any], request: EvaluateCandidatesRequest) -> str:
    valid = {member.value for member in EvaluationDecision}
    raw = payload.get("decision")
    if isinstance(raw, str):
        cleaned = raw.strip().lower().replace("-", "_").replace(" ", "_")
        if cleaned in valid:
            return cleaned
        if cleaned in _DECISION_ALIASES:
            return _DECISION_ALIASES[cleaned]

    # The model's json_object response occasionally omits `decision` (or
    # returns a value outside the enum). Infer it from whichever decision
    # payload the model did populate, so a valid selection isn't discarded.
    if isinstance(payload.get("final_classification"), dict):
        return EvaluationDecision.SELECT_CANDIDATE.value
    selected_code = payload.get("selected_code") or payload.get("code")
    if selected_code and _build_final_classification_from_selected_code(
        selected_code=str(selected_code),
        selected_label=None,
        selection_reason="",
        request=request,
    ):
        return EvaluationDecision.SELECT_CANDIDATE.value
    if isinstance(payload.get("re_search_unspsc"), dict):
        return EvaluationDecision.RE_SEARCH_UNSPSC.value
    if isinstance(payload.get("web_search"), dict):
        return EvaluationDecision.WEB_SEARCH.value

    # Nothing to infer from - treat as "couldn't decide" instead of crashing
    # the whole pipeline stage with a KeyError/ValueError.
    return EvaluationDecision.UNABLE_TO_RESOLVE.value


def _default_candidate_set_diagnosis(decision: str) -> str:
    if decision == "select_candidate":
        return "correct_candidate_present"
    if decision == "re_search_unspsc":
        return "no_viable_candidate"
    if decision == "web_search":
        return "item_identity_unresolved"
    return "insufficient_evidence_impossible"


def _build_final_classification_from_selected_code(
    *,
    selected_code: str,
    selected_label: Optional[str],
    selection_reason: str,
    request: EvaluateCandidatesRequest,
) -> Optional[dict[str, Any]]:
    for candidate in request.unspsc_search_output.get("candidates", []):
        if candidate.get("code") == selected_code:
            return {
                "selection_source": "retrieved_candidate",
                "code": selected_code,
                "label": selected_label or candidate.get("label") or selected_code,
                "source_candidate_code": None,
                "source_candidate_label": None,
                "fit": "acceptable",
                "classification_confidence": "medium",
                "selection_reason": selection_reason,
                "alternative_rejection_summary": None,
            }
        hierarchy_path = candidate.get("hierarchy_path") or {}
        for level_name in ("segment", "family", "class", "commodity"):
            node = hierarchy_path.get(level_name)
            if isinstance(node, dict) and node.get("code") == selected_code:
                return {
                    "selection_source": "hierarchy_parent",
                    "code": selected_code,
                    "label": selected_label or node.get("label") or selected_code,
                    "source_candidate_code": candidate.get("code"),
                    "source_candidate_label": candidate.get("label"),
                    "fit": "acceptable",
                    "classification_confidence": "medium",
                    "selection_reason": selection_reason,
                    "alternative_rejection_summary": None,
                }
    return None