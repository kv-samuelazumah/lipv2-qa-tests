"""Mark HMRC tax penalties for spend exclusion and review: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '006',
    'title': 'Mark HMRC tax penalties for spend exclusion and review',
    'source_id': 'E2E-06',
    'mode': 'rule',
    'rule': {   'label': 'HMRC Tax Penalty',
                'order': 6,
                'status': 'REVIEW_REQUIRED',
                'policy': 'exclude_from_spend_review_required',
                'code': '-2000',
                'level': 'SEGMENT'}}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "006_fixture_mark_hmrc_tax_penalties_for_spend_exclusion_and_review.jsonl")
