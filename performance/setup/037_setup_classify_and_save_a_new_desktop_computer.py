"""Classify and save a new desktop computer: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '037',
    'title': 'Classify and save a new desktop computer',
    'source_id': 'E2E-37',
    'preconditions': 'No matching supplier/item lookup or active Non-UNSPSC rule at the start. '
                     'Relevant corpus candidates available. Use a supported positive selection for '
                     '43211507.',
    'expected': '1. No saved answer or rule matches. Identify recognises a finished desktop '
                'computer, and Search returns relevant candidates.\n'
                ' 2. Evaluation selects code 43211507. The final result is MATCH_OBTAINED and '
                'SOLVED.\n'
                ' 3. One classification is saved with the current organisation in its agreement '
                'list. The answer remains organisation-specific (stable=false).',
    'mode': 'agentic',
    'code': '43211507',
    'fresh': True,
    'identity_terms': ['desktop']}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "037_fixture_classify_and_save_a_new_desktop_computer.jsonl")
