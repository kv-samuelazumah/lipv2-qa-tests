"""Share a saved classification with a new organisation: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '033',
    'title': 'Share a saved classification with a new organisation',
    'source_id': 'E2E-33',
    'preconditions': 'Seed an approved corpus-backed Acme Ltd / Laser printers, solved_for '
                     'contains only organisations 111…, 222…, 333…. Record exact fixture '
                     'ID/code/level.',
    'expected': '1. Organisation 44444444-4444-4444-4444-444444444444 receives STABLE_LOOKUP with '
                'status SOLVED.\n'
                ' 2. The row ID, code, level and policy match the prepared shared classification.\n'
                ' 3. The new organisation does not need to appear in the saved agreement list. '
                'Identify, Search and Evaluation do not run.',
    'mode': 'lookup',
    'stable': True,
    'solved_for': [   '11111111-1111-1111-1111-111111111111',
                      '22222222-2222-2222-2222-222222222222',
                      '33333333-3333-3333-3333-333333333333'],
    'new_org': True,
    'label': 'Laser printers'}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "033_fixture_share_a_saved_classification_with_a_new_organisation.jsonl")
