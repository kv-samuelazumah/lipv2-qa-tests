"""Send service charges for human review: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '021',
    'title': 'Send service charges for human review',
    'source_id': 'E2E-21',
    'mode': 'rule',
    'rule': {   'label': 'Generic Service Charge',
                'order': 21,
                'status': 'REVIEW_REQUIRED',
                'policy': 'review_required',
                'code': '-3000',
                'level': 'SEGMENT'}}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "021_fixture_send_service_charges_for_human_review.jsonl")
