"""Mark parking penalty notices for spend exclusion and review: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '008',
    'title': 'Mark parking penalty notices for spend exclusion and review',
    'source_id': 'E2E-08',
    'mode': 'rule',
    'rule': {   'label': 'Parking',
                'order': 8,
                'status': 'REVIEW_REQUIRED',
                'policy': 'exclude_from_spend_review_required',
                'code': '-2000',
                'level': 'SEGMENT'}}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "008_fixture_mark_parking_penalty_notices_for_spend_exclusion_and_review.jsonl")
