"""Keep repeated requests from counting as new agreements: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '040',
    'title': 'Keep repeated requests from counting as new agreements',
    'source_id': 'E2E-40',
    'preconditions': 'No matching supplier/item lookup or active Non-UNSPSC rule at the start. '
                     'Relevant corpus candidates available. First run successfully selects '
                     'supported 56101720.',
    'expected': '1. The first request returns SOLVED with code 56101720 for the office chair.\n'
                ' 2. Later requests from the same organisation reuse the organisation-specific '
                'answer.\n'
                ' 3. Only one saved row exists, and the organisation appears once in its agreement '
                'list. The answer remains stable=false.',
    'mode': 'repeat',
    'code': '56101720'}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "040_fixture_keep_repeated_requests_from_counting_as_new_agreements.jsonl")
