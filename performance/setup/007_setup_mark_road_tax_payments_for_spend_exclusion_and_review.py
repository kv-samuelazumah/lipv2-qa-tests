"""Mark road tax payments for spend exclusion and review: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '007',
    'title': 'Mark road tax payments for spend exclusion and review',
    'source_id': 'E2E-07',
    'mode': 'rule',
    'rule': {   'label': 'Road Tax',
                'order': 7,
                'status': 'REVIEW_REQUIRED',
                'policy': 'exclude_from_spend_review_required',
                'code': '-2000',
                'level': 'SEGMENT'}}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "007_fixture_mark_road_tax_payments_for_spend_exclusion_and_review.jsonl")
