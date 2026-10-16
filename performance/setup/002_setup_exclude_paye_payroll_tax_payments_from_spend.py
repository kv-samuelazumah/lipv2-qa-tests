"""Exclude PAYE payroll tax payments from spend: rule expectations for the live application."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '002',
    'title': 'Exclude PAYE payroll tax payments from spend',
    'source_id': 'E2E-02',
    'mode': 'rule',
    'rule': {   'label': 'PAYE',
                'order': 3,
                'status': 'EXCLUDED',
                'policy': 'exclude_from_spend',
                'code': '-1000',
                'level': 'SEGMENT'}}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "002_fixture_exclude_paye_payroll_tax_payments_from_spend.jsonl")
