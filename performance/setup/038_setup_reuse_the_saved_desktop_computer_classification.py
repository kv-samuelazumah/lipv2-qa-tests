"""Reuse the saved desktop computer classification: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '038',
    'title': 'Reuse the saved desktop computer classification',
    'source_id': 'E2E-38',
    'preconditions': 'E2E-37 has saved an organisation-specific desktop computer classification '
                     'for organisation 11111111-1111-1111-1111-111111111111. Record its row ID and '
                     'lookup hash.',
    'expected': '1. The same organisation receives UNSTABLE_LOOKUP with status SOLVED, using the '
                'same saved row and code.\n'
                ' 2. Identify, Search and Evaluation do not run.\n'
                ' 3. No duplicate classification is created.',
    'mode': 'lookup',
    'code': '43211507',
    'stable': False}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "038_fixture_reuse_the_saved_desktop_computer_classification.jsonl")
