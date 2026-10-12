from __future__ import annotations

import hashlib
import re


_WHITESPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^\w\s]")


def normalize_supplier(value: str) -> str:
    return _normalize_text(value)


def normalize_line_item(value: str) -> str:
    return _normalize_text(value)


def build_lookup_hash(supplier_normalized: str, line_item_normalized: str) -> str:
    payload = f"{supplier_normalized}::{line_item_normalized}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_text(value: str) -> str:
    lowered = (value or "").strip().lower()
    stripped = _NON_WORD_RE.sub(" ", lowered)
    return _WHITESPACE_RE.sub(" ", stripped).strip()
