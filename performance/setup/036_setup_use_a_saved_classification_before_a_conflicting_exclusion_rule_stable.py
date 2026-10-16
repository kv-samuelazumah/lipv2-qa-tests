"""Use a saved classification before a conflicting exclusion rule: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '036',
    'title': 'Use a saved classification before a conflicting exclusion rule',
    'source_id': 'E2E-36',
    'preconditions': 'Configure lookup 43222609 / SOLVED and matching active EXCLUDED / -1000 '
                     'rule. Separately run unstable (111… only) and stable (111…,222…,333…) '
                     'fixtures. Record both IDs.',
    'expected': '1. Run once with the organisation-specific fixture and once with the shared '
                'fixture. Each run returns the appropriate lookup type and prepared row ID.\n'
                ' 2. Both results are SOLVED with code 43222609 at COMMODITY level.\n'
                ' 3. The conflicting exclusion rule is not applied. Identify, Search and '
                'Evaluation do not run.',
    'mode': 'lookup',
    'code': '43222609',
    'conflicting_rule': True,
    'stable': True,
    'solved_for': [   '11111111-1111-1111-1111-111111111111',
                      '22222222-2222-2222-2222-222222222222',
                      '33333333-3333-3333-3333-333333333333']}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "036_fixture_use_a_saved_classification_before_a_conflicting_exclusion_rule_stable.jsonl")
