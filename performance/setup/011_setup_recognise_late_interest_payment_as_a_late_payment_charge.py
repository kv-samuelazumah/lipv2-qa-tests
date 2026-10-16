"""Recognise “late interest payment” as a late payment charge: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '011',
    'title': 'Recognise “late interest payment” as a late payment charge',
    'source_id': 'E2E-11',
    'mode': 'rule',
    'rule': {   'label': 'Late Payment',
                'order': 10,
                'status': 'REVIEW_REQUIRED',
                'policy': 'exclude_from_spend_review_required',
                'code': '-2000',
                'level': 'SEGMENT'}}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "011_fixture_recognise_late_interest_payment_as_a_late_payment_charge.jsonl")
