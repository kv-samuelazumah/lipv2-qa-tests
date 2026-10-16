"""Leave whitespace-only and symbol-only descriptions unresolved: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '031',
    'title': 'Leave whitespace-only and symbol-only descriptions unresolved',
    'source_id': 'E2E-31',
    'preconditions': 'The application can connect to the test database. No alternative description '
                     'field is provided. For blank or symbol-only text, there is no reusable saved '
                     'answer for an empty normalized description.',
    'expected': '1. Both non-empty strings are accepted. No saved answer or rule matches; '
                'pre_agentic_result is null.\n'
                ' 2. Identify and Search run. Evaluation runs when candidates are available.\n'
                ' 3. The final stage is UNABLE_TO_RESOLVE and the status is UNRESOLVED. No code, '
                'level or exclusion policy is returned.\n'
                ' 4. The reason may contain an explanation or be empty; the current implementation '
                'permits either.\n'
                ' 5. No successful classification is saved. Both variants must meet these '
                'expectations for the grouped case to pass.',
    'mode': 'agentic',
    'continue_on_failure': True,
    'unresolved': True}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "031_fixture_leave_whitespace_only_and_symbol_only_descriptions_unresolved.jsonl")
