"""Send penalties and fines for human review: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '022',
    'title': 'Send penalties and fines for human review',
    'source_id': 'E2E-22',
    'mode': 'rule',
    'rule': {   'label': 'Generic Penalty Fine',
                'order': 22,
                'status': 'REVIEW_REQUIRED',
                'policy': 'review_required',
                'code': '-3000',
                'level': 'SEGMENT'}}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "022_fixture_send_penalties_and_fines_for_human_review.jsonl")
