"""Send donations for human review: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '020',
    'title': 'Send donations for human review',
    'source_id': 'E2E-20',
    'mode': 'rule',
    'rule': {   'label': 'Donation / Charitable Contribution',
                'order': 19,
                'status': 'REVIEW_REQUIRED',
                'policy': 'review_required',
                'code': '-3000',
                'level': 'SEGMENT'}}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "020_fixture_send_donations_for_human_review.jsonl")
