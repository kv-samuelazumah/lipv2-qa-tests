"""Exclude refunds from classification: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '014',
    'title': 'Exclude refunds from classification',
    'source_id': 'E2E-14',
    'mode': 'rule',
    'rule': {   'label': 'Refund / Credit',
                'order': 12,
                'status': 'EXCLUDED',
                'policy': 'exclude_from_classification',
                'code': '-4000',
                'level': 'SEGMENT'}}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "014_fixture_exclude_refunds_from_classification.jsonl")
