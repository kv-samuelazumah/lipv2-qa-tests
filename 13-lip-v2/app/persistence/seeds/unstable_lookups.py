from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from ...pre_agentic.normalize import build_lookup_hash, normalize_line_item, normalize_supplier


_supplier = "Acme Ltd"
_line_item = "Local area trucking services"
_supplier_normalized = normalize_supplier(_supplier)
_line_item_normalized = normalize_line_item(_line_item)
_lookup_hash = build_lookup_hash(_supplier_normalized, _line_item_normalized)
_cleaning_line_item = "Building cleaning services"
_cleaning_normalized = normalize_line_item(_cleaning_line_item)
_cleaning_lookup_hash = build_lookup_hash(_supplier_normalized, _cleaning_normalized)

UNSTABLE_LOOKUP_SEEDS = [
    {
        "id": str(uuid5(NAMESPACE_URL, f"13-lip-v2/unstable-lookup/{_lookup_hash}")),
        "lookup_hash": _lookup_hash,
        "supplier_raw": _supplier,
        "supplier_normalized": _supplier_normalized,
        "line_item_raw": _line_item,
        "line_item_normalized": _line_item_normalized,
        "solved_for": ["11111111-1111-1111-1111-111111111111"],
        "unspsc_code": "78101801",
        "unspsc_level": "COMMODITY",
        "policy_code": None,
        "status_code": "SOLVED",
        "source_type": "SEED",
        "reasoning": {
            "selected_label": "Local area trucking services",
            "notes": "Sample unstable lookup matching unspsc-search-corpus-v260801.1.jsonl.",
        },
    },
    {
        "id": str(uuid5(NAMESPACE_URL, f"13-lip-v2/unstable-lookup/{_cleaning_lookup_hash}")),
        "lookup_hash": _cleaning_lookup_hash,
        "supplier_raw": _supplier,
        "supplier_normalized": _supplier_normalized,
        "line_item_raw": _cleaning_line_item,
        "line_item_normalized": _cleaning_normalized,
        "solved_for": ["11111111-1111-1111-1111-111111111111"],
        "unspsc_code": "76111501",
        "unspsc_level": "COMMODITY",
        "policy_code": None,
        "status_code": "SOLVED",
        "source_type": "SEED",
        "reasoning": {
            "selected_label": _cleaning_line_item,
            "notes": "Sample unstable lookup for organisation-isolation QA testing.",
        },
    },
]
