"""Reject empty, null and missing descriptions: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '030',
    'title': 'Reject empty, null and missing descriptions',
    'source_id': 'E2E-30',
    'preconditions': 'The application can connect to the test database. No alternative description '
                     'field is provided. For blank or symbol-only text, there is no reusable saved '
                     'answer for an empty normalized description.',
    'expected': '1. Each variant is rejected with a ValueError stating that a line item text field '
                'is required. The single-item command exits with a non-zero code.\n'
                ' 2. Identify, Search and Evaluation do not run, and no classification is saved.\n'
                ' 3. Database initialization and seeding may run before the input error is '
                'reported; this is normal for the current CLI.',
    'mode': 'invalid'}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "030_fixture_reject_empty_null_and_missing_descriptions.jsonl")
