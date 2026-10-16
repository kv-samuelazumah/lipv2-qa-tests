"""Mark late payment interest for spend exclusion and review: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '009',
    'title': 'Mark late payment interest for spend exclusion and review',
    'source_id': 'E2E-09',
    'mode': 'rule',
    'rule': {   'label': 'Late Payment',
                'order': 10,
                'status': 'REVIEW_REQUIRED',
                'policy': 'exclude_from_spend_review_required',
                'code': '-2000',
                'level': 'SEGMENT'}}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "009_fixture_mark_late_payment_interest_for_spend_exclusion_and_review.jsonl")
