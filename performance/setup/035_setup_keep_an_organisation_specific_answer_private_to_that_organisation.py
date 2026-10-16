"""Keep an organisation-specific answer private to that organisation: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '035',
    'title': 'Keep an organisation-specific answer private to that organisation',
    'source_id': 'E2E-35',
    'preconditions': 'An unstable lookup exists for Clearway Cleaning Services / Building cleaning '
                     'services, with code 76111501 / COMMODITY, status SOLVED, and stable=false. '
                     'Reset and verify solved_for contains only organisation 111…; organisation '
                     '222… must be absent. No active Non-UNSPSC rule matches the item. Run '
                     'organisation 222… once after the reset and capture its first response, '
                     'because a successful classification may add it to solved_for.',
    'expected': '1. Organisation 22222222-2222-2222-2222-222222222222 does not reuse the first '
                'organisation’s answer; pre_agentic_result is null.\n'
                ' 2. Identify, Search and Evaluation run.\n'
                ' 3. If the same code 76111501 is selected, the existing row records the second '
                'organisation once. With two organisations, the answer remains '
                'organisation-specific (stable=false).\n'
                ' 4. If a different code is selected, the row is updated and its agreement list '
                'restarts with only the second organisation.\n'
                ' 5. If the result is unresolved, no successful classification or new agreement is '
                'saved.',
    'mode': 'isolation',
    'old_code': '76111501',
    'old_orgs': ['11111111-1111-1111-1111-111111111111']}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "035_fixture_keep_an_organisation_specific_answer_private_to_that_organisation.jsonl")
