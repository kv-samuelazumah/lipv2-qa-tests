"""Process every batch item even when one input is invalid: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '044',
    'title': 'Process every batch item even when one input is invalid',
    'source_id': 'E2E-44',
    'preconditions': 'Active PAYE rule; stable Papertrail pen lookup; no saved answer or matching '
                     'rule for the pump; live classification services and search corpus available.',
    'expected': '1. Four results are returned in input order: PAYE exclusion, a '
                'missing-description error, the shared pen classification, and the pump '
                'classification outcome.\n'
                ' 2. The invalid second item does not stop the third or fourth item.\n'
                ' 3. The pump may be SOLVED as Pump parts and accessories (40151700 at CLASS '
                'level) when supported by retrieved evidence. The selected classification must be '
                'saved for the requesting organisation.\n'
                ' 4. If evidence is insufficient, the pump remains UNRESOLVED with no code or '
                'saved classification. No classification is saved for the invalid item in either '
                'case.',
    'mode': 'batch',
    'pump_code': '40151700',
    'pump_level': 'CLASS'}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "044_fixture_process_every_batch_item_even_when_one_input_is_invalid.jsonl")
