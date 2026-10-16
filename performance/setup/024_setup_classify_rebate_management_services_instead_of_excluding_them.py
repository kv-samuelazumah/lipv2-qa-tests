"""Classify rebate management services instead of excluding them: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '024',
    'title': 'Classify rebate management services instead of excluding them',
    'source_id': 'E2E-24',
    'preconditions': 'The application can connect to the test database. The Rebate Amount rule is '
                     'enabled. There is no reusable saved classification or other matching rule '
                     'for this input. Identify, Search and Evaluation are configured and '
                     'available, with relevant service candidates in the search corpus.',
    'expected': '1. The command finishes without errors.\n'
                ' 2. The Rebate Amount rule is bypassed; pre_agentic_result is null and exclusion '
                'code -5000 is not applied.\n'
                ' 3. Identify and Search run. Evaluation runs when candidates are available.\n'
                ' 4. The result contains a supported service classification, or UNRESOLVED if the '
                'evidence is insufficient. No specific service code is required by this case.',
    'mode': 'agentic',
    'service': True}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "024_fixture_classify_rebate_management_services_instead_of_excluding_them.jsonl")
