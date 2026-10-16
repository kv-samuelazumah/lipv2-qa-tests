"""Recognise network routers despite a spelling typo: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '025',
    'title': 'Recognise network routers despite a spelling typo',
    'source_id': 'E2E-25',
    'preconditions': 'The database and agentic services are available. The search corpus contains '
                     'Network routers (43222609). No saved classification or exclusion rule '
                     'matches this input.',
    'expected': '1. The command finishes without errors. No saved answer or exclusion rule '
                'matches; pre_agentic_result is null.\n'
                ' 2. Identify recognises the intended network router product, and Search retrieves '
                'a relevant candidate.\n'
                ' 3. The final result is MATCH_OBTAINED and SOLVED, with code 43222609 at '
                'COMMODITY level, label Network routers and no exclusion policy.\n'
                ' 4. The successful classification is saved for the supplier, description and '
                'organisation. A broader CLASS result does not meet this case’s expected commodity '
                'result.',
    'mode': 'agentic',
    'code': '43222609',
    'label': 'Network routers',
    'fresh': True,
    'identity_terms': ['router']}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "025_fixture_recognise_network_routers_despite_a_spelling_typo.jsonl")
