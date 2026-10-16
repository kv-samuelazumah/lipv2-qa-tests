"""Exclude council tax payments from spend: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '004',
    'title': 'Exclude council tax payments from spend',
    'source_id': 'E2E-04',
    'mode': 'rule',
    'rule': {   'label': 'Council Tax',
                'order': 4,
                'status': 'EXCLUDED',
                'policy': 'exclude_from_spend',
                'code': '-1000',
                'level': 'SEGMENT'}}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "004_fixture_exclude_council_tax_payments_from_spend.jsonl")
