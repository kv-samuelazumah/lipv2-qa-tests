"""Leave an unclear adjustment unresolved: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '043',
    'title': 'Leave an unclear adjustment unresolved',
    'source_id': 'E2E-43',
    'preconditions': 'No matching supplier/item lookup or active Non-UNSPSC rule at the start. '
                     'Relevant corpus candidates available. No usable external evidence; '
                     'controlled justified unresolved result.',
    'expected': '1. No unsupported product identity or category is selected.\n'
                ' 2. The final status is UNRESOLVED, with no classification code or level. A '
                'reason may be supplied or left empty by the current implementation.\n'
                ' 3. No successful classification is saved.',
    'mode': 'agentic',
    'unresolved': True}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "043_fixture_leave_an_unclear_adjustment_unresolved.jsonl")
