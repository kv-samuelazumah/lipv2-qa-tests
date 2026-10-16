"""Mark rebate amounts for exclusion and review: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '023',
    'title': 'Mark rebate amounts for exclusion and review',
    'source_id': 'E2E-23',
    'mode': 'rule',
    'rule': {   'label': 'Rebate Amount',
                'order': 13,
                'status': 'REVIEW_REQUIRED',
                'policy': 'exclude_from_classification_unless_service',
                'code': '-5000',
                'level': 'SEGMENT'}}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "023_fixture_mark_rebate_amounts_for_exclusion_and_review.jsonl")
