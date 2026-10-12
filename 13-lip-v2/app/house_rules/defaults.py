from __future__ import annotations

from typing import Dict, List


DEFAULT_HOUSE_RULES: List[Dict[str, str]] = [
    {"rule_name": "HR001", "rule": "Classify the primary purchased deliverable. The line's main item or service is the target."},
    {"rule_name": "HR002", "rule": "Do not classify incidental specs, components, colours, dimensions, capacities or included features unless they are the purchased item."},
    {"rule_name": "HR003", "rule": "Finished product beats raw material, unless the raw material itself is being purchased."},
    {"rule_name": "HR004", "rule": "Functional component or part beats the finished product it is for."},
    {"rule_name": "HR005", "rule": "Accessory, spare, or consumable beats the main equipment it supports."},
    {"rule_name": "HR006", "rule": "The phrase 'for X' usually means compatibility or use context, not that X is the purchased item."},
    {"rule_name": "HR007", "rule": "Distinguish product from service."},
    {"rule_name": "HR008", "rule": "Distinguish service from physical goods involved in the service."},
    {"rule_name": "HR009", "rule": "Distinguish rental, hire, or lease from purchase of the underlying item."},
    {"rule_name": "HR010", "rule": "Distinguish software, SaaS, subscription, or licence from physical goods and from public or admin licence fees."},
    {"rule_name": "HR011", "rule": "Public or admin licence or registration fee is different from software licence, vehicle tax, permit, membership, or subscription."},
    {"rule_name": "HR012", "rule": "Kits or bundles should be classified by stated kit purpose where clear."},
    {"rule_name": "HR013", "rule": "Mixed unrelated lines should not be forced into one specific commodity."},
    {"rule_name": "HR014", "rule": "Classify by product function before brand."},
    {"rule_name": "HR015", "rule": "Do not classify from brand alone."},
    {"rule_name": "HR016", "rule": "Do not classify from attributes alone."},
    {"rule_name": "HR017", "rule": "Use the most specific UNSPSC level supported by the item evidence."},
    {"rule_name": "HR018", "rule": "If a candidate includes unsupported detail, use the supported parent rather than over-classifying."},
    {"rule_name": "HR019", "rule": "If the item is a raw or bulk material, stock, scrap, waste, fabric, fibre, ore, sand, soil, alloy, or timber, raw-material UNSPSC areas may be valid."},
    {"rule_name": "HR020", "rule": "If material wording only describes what a finished product or component is made of, do not classify as raw material."},
]


def merge_house_rules(custom_rules: List[Dict[str, str]]) -> List[Dict[str, str]]:
    merged: List[Dict[str, str]] = []
    seen: set[str] = set()
    for rule in DEFAULT_HOUSE_RULES + list(custom_rules or []):
        rule_name = str(rule.get("rule_name") or "").strip()
        rule_text = str(rule.get("rule") or "").strip()
        if not rule_name or not rule_text or rule_name in seen:
            continue
        merged.append({"rule_name": rule_name, "rule": rule_text})
        seen.add(rule_name)
    return merged
