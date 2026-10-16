"""Mark tips for spend exclusion and review: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '012',
    'title': 'Mark tips for spend exclusion and review',
    'source_id': 'E2E-12',
    'mode': 'rule',
    'rule': {   'label': 'Tip / Gratuity',
                'order': 20,
                'status': 'REVIEW_REQUIRED',
                'policy': 'exclude_from_spend_review_required',
                'code': '-2000',
                'level': 'SEGMENT'}}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "012_fixture_mark_tips_for_spend_exclusion_and_review.jsonl")
