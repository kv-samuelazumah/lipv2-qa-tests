"""Mark security deposits for spend exclusion and review: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '010',
    'title': 'Mark security deposits for spend exclusion and review',
    'source_id': 'E2E-10',
    'mode': 'rule',
    'rule': {   'label': 'Security',
                'order': 17,
                'status': 'REVIEW_REQUIRED',
                'policy': 'exclude_from_spend_review_required',
                'code': '-2000',
                'level': 'SEGMENT'}}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "010_fixture_mark_security_deposits_for_spend_exclusion_and_review.jsonl")
