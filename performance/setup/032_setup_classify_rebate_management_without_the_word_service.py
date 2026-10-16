"""Classify rebate management without the word “service”: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '032',
    'title': 'Classify rebate management without the word “service”',
    'source_id': 'E2E-32',
    'preconditions': 'The application and database are available. The Rebate Amount rule is '
                     'enabled. No saved classification or other rule matches this supplier and '
                     'description. Identify, Search, and Evaluation are available.',
    'expected': '1. The Rebate Amount rule is bypassed; pre_agentic_result is null and code -5000 '
                'is not applied.\n'
                ' 2. Identify and Search run. Evaluation runs when candidates are available.\n'
                ' 3. The final result contains a supported classification, or UNRESOLVED if '
                'evidence is insufficient. The word service is not required for the rebate '
                'management exception.',
    'mode': 'agentic',
    'service': True}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "032_fixture_classify_rebate_management_without_the_word_service.jsonl")
