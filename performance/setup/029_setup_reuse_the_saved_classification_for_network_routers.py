"""Reuse the saved classification for Network_routers: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '029',
    'title': 'Reuse the saved classification for Network_routers',
    'source_id': 'E2E-29',
    'preconditions': 'The application can connect to the test database. An organisation-specific '
                     'answer for Harbour Network Supplies / Network_routers is saved for '
                     'organisation 11111111-1111-1111-1111-111111111111, with code 43222609 at '
                     'COMMODITY level, label Network routers and status SOLVED. Record its row ID '
                     'and lookup hash.',
    'expected': '1. The command finishes without errors and reuses the saved Network_routers row.\n'
                ' 2. The response shows PRE_AGENTIC_HIT and UNSTABLE_LOOKUP. The row ID and lookup '
                'hash match the saved underscore description.\n'
                ' 3. The final result is SOLVED, with code 43222609 at COMMODITY level, label '
                'Network routers and no exclusion policy.\n'
                ' 4. Identify, Search and Evaluation do not run; their results are null. No '
                'duplicate classification is created.',
    'mode': 'lookup',
    'code': '43222609',
    'label': 'Network routers',
    'stable': False}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "029_fixture_reuse_the_saved_classification_for_network_routers.jsonl")
