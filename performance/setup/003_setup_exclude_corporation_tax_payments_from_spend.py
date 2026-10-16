"""Exclude corporation tax payments from spend: rule expectations for the live application."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '003',
    'title': 'Exclude corporation tax payments from spend',
    'source_id': 'E2E-03',
    'mode': 'rule',
    'rule': {   'label': 'Generic Tax Payment',
                'order': 2,
                'status': 'EXCLUDED',
                'policy': 'exclude_from_spend',
                'code': '-1000',
                'level': 'SEGMENT'}}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "003_fixture_exclude_corporation_tax_payments_from_spend.jsonl")
