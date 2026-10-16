"""Exclude discounts from classification: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '013',
    'title': 'Exclude discounts from classification',
    'source_id': 'E2E-13',
    'mode': 'rule',
    'rule': {   'label': 'Discount / Coupon',
                'order': 11,
                'status': 'EXCLUDED',
                'policy': 'exclude_from_classification',
                'code': '-4000',
                'level': 'SEGMENT'}}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "013_fixture_exclude_discounts_from_classification.jsonl")
