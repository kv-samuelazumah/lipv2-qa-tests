"""Classify toner as a consumable rather than a printer: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '042',
    'title': 'Classify toner as a consumable rather than a printer',
    'source_id': 'E2E-42',
    'preconditions': 'No matching supplier/item lookup or active Non-UNSPSC rule at the start. '
                     'Relevant corpus candidates available. Provide relevant toner candidates; '
                     'approved positive code 44103103.',
    'expected': '1. Identify recognises toner as the purchased item.\n'
                ' 2. The final classification uses the supported toner code 44103103.\n'
                ' 3. A complete-printer classification is not selected or saved.',
    'mode': 'agentic',
    'code': '44103103',
    'fresh': True,
    'identity_terms': ['toner']}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "042_fixture_classify_toner_as_a_consumable_rather_than_a_printer.jsonl")
