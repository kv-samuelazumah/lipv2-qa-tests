"""Reset prior agreements when the classification changes: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '041',
    'title': 'Reset prior agreements when the classification changes',
    'source_id': 'E2E-41',
    'preconditions': 'Seed intentionally conflicting old 43212105 / COMMODITY, stable=false, '
                     'solved_for=[111…,222…]. No matching rule. Control organisation 444… to '
                     'select retrieved 44101501.',
    'expected': '1. For the prepared supplier and item, organisation '
                '44444444-4444-4444-4444-444444444444 selects code 44101501, replacing the old '
                'code in the existing row.\n'
                ' 2. The prior agreements are removed. Only the organisation that selected the new '
                'code remains in the agreement list, and stable=false.\n'
                ' 3. That organisation can reuse the new answer. An organisation that agreed only '
                'with the old code must classify the item again.\n'
                ' 4. All commands must use the same supplier and description, and the change '
                'request must come from organisation 44444444-4444-4444-4444-444444444444. The '
                'current Test Data commands do not satisfy these conditions and need correction '
                'before execution.',
    'mode': 'change',
    'code': '44101501',
    'old_code': '43212105',
    'old_orgs': ['11111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222'],
    'input_correction': 'Use Metro Office Equipment Supplies for every call; change and reuse come '
                        'from organisation 444, then prior organisation 111.'}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "041_fixture_reset_prior_agreements_when_the_classification_changes.jsonl")
