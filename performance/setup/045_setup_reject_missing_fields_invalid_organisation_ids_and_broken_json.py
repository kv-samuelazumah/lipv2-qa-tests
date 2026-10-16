"""Reject missing fields, invalid organisation IDs and broken JSON: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '045',
    'title': 'Reject missing fields, invalid organisation IDs and broken JSON',
    'source_id': 'E2E-45',
    'preconditions': 'Independent scenarios; record database state before each.',
    'expected': '1. Missing organisation IDs, invalid UUIDs, and missing or empty descriptions are '
                'rejected.\n'
                ' 2. Malformed JSON is rejected during parsing.\n'
                ' 3. Each single-item command exits with an error. No classification is selected '
                'or saved for the invalid input. Database initialization and seeding may still '
                'occur before validation.',
    'mode': 'invalid'}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "045_fixture_reject_missing_fields_invalid_organisation_ids_and_broken_json.jsonl")
