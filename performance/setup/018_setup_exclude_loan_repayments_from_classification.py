"""Exclude loan repayments from classification: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '018',
    'title': 'Exclude loan repayments from classification',
    'source_id': 'E2E-18',
    'mode': 'rule',
    'rule': {   'label': 'Loan / Debt Repayment',
                'order': 18,
                'status': 'EXCLUDED',
                'policy': 'exclude_from_classification',
                'code': '-4200',
                'level': 'SEGMENT'}}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "018_fixture_exclude_loan_repayments_from_classification.jsonl")
