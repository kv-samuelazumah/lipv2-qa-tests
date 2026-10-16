"""Send ULEZ charges for human review: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '019',
    'title': 'Send ULEZ charges for human review',
    'source_id': 'E2E-19',
    'mode': 'rule',
    'rule': {   'label': 'ULEZ',
                'order': 9,
                'status': 'REVIEW_REQUIRED',
                'policy': 'review_required',
                'code': '-3000',
                'level': 'SEGMENT'}}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "019_fixture_send_ulez_charges_for_human_review.jsonl")
