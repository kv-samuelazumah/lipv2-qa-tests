"""Exclude VAT payments from spend: rule expectations for the live application."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '001',
    'title': 'Exclude VAT payments from spend',
    'source_id': 'E2E-01',
    'mode': 'rule',
    'rule': {   'label': 'VAT',
                'order': 1,
                'status': 'EXCLUDED',
                'policy': 'exclude_from_spend',
                'code': '-1000',
                'level': 'SEGMENT'}}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "001_fixture_exclude_vat_payments_from_spend.jsonl")
