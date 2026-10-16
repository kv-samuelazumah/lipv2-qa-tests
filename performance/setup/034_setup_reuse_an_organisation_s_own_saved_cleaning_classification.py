"""Reuse an organisation’s own saved cleaning classification: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '034',
    'title': 'Reuse an organisation’s own saved cleaning classification',
    'source_id': 'E2E-34',
    'preconditions': 'Seed 76111501 / COMMODITY, SOLVED, stable=false, solved_for=[organisation '
                     '111…]; record fixture ID.',
    'expected': '1. The organisation receives UNSTABLE_LOOKUP with status SOLVED.\n'
                ' 2. The result uses the prepared row, code 76111501 at COMMODITY level, and '
                'stable=false.\n'
                ' 3. Identify, Search and Evaluation do not run.',
    'mode': 'lookup',
    'code': '76111501',
    'stable': False,
    'solved_for': ['11111111-1111-1111-1111-111111111111']}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "034_fixture_reuse_an_organisation_s_own_saved_cleaning_classification.jsonl")
