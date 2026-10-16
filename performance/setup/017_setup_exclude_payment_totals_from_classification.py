"""Exclude payment totals from classification: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '017',
    'title': 'Exclude payment totals from classification',
    'source_id': 'E2E-17',
    'mode': 'rule',
    'rule': {   'label': 'Payment / Tender Row',
                'order': 16,
                'status': 'EXCLUDED',
                'policy': 'exclude_from_classification',
                'code': '-4000',
                'level': 'SEGMENT'}}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "017_fixture_exclude_payment_totals_from_classification.jsonl")
