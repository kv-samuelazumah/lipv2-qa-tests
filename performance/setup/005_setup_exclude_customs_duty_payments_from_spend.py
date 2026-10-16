"""Exclude customs duty payments from spend: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '005',
    'title': 'Exclude customs duty payments from spend',
    'source_id': 'E2E-05',
    'mode': 'rule',
    'rule': {   'label': 'Custom Imports',
                'order': 5,
                'status': 'EXCLUDED',
                'policy': 'exclude_from_spend',
                'code': '-1000',
                'level': 'SEGMENT'}}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "005_fixture_exclude_customs_duty_payments_from_spend.jsonl")
