from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from ...pre_agentic.normalize import build_lookup_hash, normalize_line_item, normalize_supplier


_supplier = "Acme Ltd"
_line_item = "Notebook"
_supplier_normalized = normalize_supplier(_supplier)
_line_item_normalized = normalize_line_item(_line_item)
_lookup_hash = build_lookup_hash(_supplier_normalized, _line_item_normalized)
_printer_line_item = "Laser printers"
_printer_normalized = normalize_line_item(_printer_line_item)
_printer_lookup_hash = build_lookup_hash(_supplier_normalized, _printer_normalized)

STABLE_LOOKUP_SEEDS = [
    {
        "id": str(uuid5(NAMESPACE_URL, f"13-lip-v2/stable-lookup/{_lookup_hash}")),
        "lookup_hash": _lookup_hash,
        "supplier_raw": _supplier,
        "supplier_normalized": _supplier_normalized,
        "line_item_raw": _line_item,
        "line_item_normalized": _line_item_normalized,
        "solved_for": [
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
            "33333333-3333-3333-3333-333333333333",
        ],
        "unspsc_code": "43211503",
        "unspsc_level": "COMMODITY",
        "policy_code": None,
        "status_code": "SOLVED",
        "source_type": "SEED",
        "reasoning": {
            "selected_label": "Notebook computer",
            "notes": "Sample stable lookup for pre-agentic validation.",
        },
    },
    {
        "id": str(uuid5(NAMESPACE_URL, f"13-lip-v2/stable-lookup/{_printer_lookup_hash}")),
        "lookup_hash": _printer_lookup_hash,
        "supplier_raw": _supplier,
        "supplier_normalized": _supplier_normalized,
        "line_item_raw": _printer_line_item,
        "line_item_normalized": _printer_normalized,
        "solved_for": [
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
            "33333333-3333-3333-3333-333333333333",
        ],
        "unspsc_code": "43212105",
        "unspsc_level": "COMMODITY",
        "policy_code": None,
        "status_code": "SOLVED",
        "source_type": "SEED",
        "reasoning": {
            "selected_label": _printer_line_item,
            "notes": "Sample stable lookup for cross-organisation QA testing.",
        },
    },
]
