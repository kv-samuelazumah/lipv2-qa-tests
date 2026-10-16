"""Exclude opening balances from classification: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '016',
    'title': 'Exclude opening balances from classification',
    'source_id': 'E2E-16',
    'mode': 'rule',
    'rule': {   'label': 'Opening Balance',
                'order': 15,
                'status': 'EXCLUDED',
                'policy': 'exclude_from_classification',
                'code': '-4000',
                'level': 'SEGMENT'}}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "016_fixture_exclude_opening_balances_from_classification.jsonl")
