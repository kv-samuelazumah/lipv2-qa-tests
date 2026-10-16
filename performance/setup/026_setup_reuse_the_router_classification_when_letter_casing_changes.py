"""Reuse the router classification when letter casing changes: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '026',
    'title': 'Reuse the router classification when letter casing changes',
    'source_id': 'E2E-26',
    'preconditions': 'The application can connect to the test database. Network routers is already '
                     'saved for Harbour Network Supplies with code 43222609 at COMMODITY level and '
                     'status SOLVED. The answer is either shared or available to this '
                     'organisation. Record its row ID and lookup hash before testing.',
    'expected': '1. Every supplied variant finishes without errors and uses the same lookup hash '
                'as Network routers.\n'
                ' 2. The same saved row is reused. The response shows PRE_AGENTIC_HIT, with '
                'STABLE_LOOKUP for a shared answer or UNSTABLE_LOOKUP for an organisation-specific '
                'answer.\n'
                ' 3. Each final result is SOLVED, with code 43222609 at COMMODITY level, label '
                'Network routers and no exclusion policy.\n'
                ' 4. Identify, Search and Evaluation do not run. Their results are null, and no '
                'duplicate classification is created.',
    'mode': 'lookup',
    'code': '43222609',
    'label': 'Network routers'}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "026_fixture_reuse_the_router_classification_when_letter_casing_changes.jsonl")
