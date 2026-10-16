"""Exclude rounding adjustments from classification: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '015',
    'title': 'Exclude rounding adjustments from classification',
    'source_id': 'E2E-15',
    'mode': 'rule',
    'rule': {   'label': 'Rounding Adjustment',
                'order': 14,
                'status': 'EXCLUDED',
                'policy': 'exclude_from_classification',
                'code': '-4000',
                'level': 'SEGMENT'}}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "015_fixture_exclude_rounding_adjustments_from_classification.jsonl")
