"""Share an answer after three organisations agree: live prerequisites and expected outcomes."""
from performance.common import ROOT
from performance.e2e import LiveCase

SPEC = {   'index': '039',
    'title': 'Share an answer after three organisations agree',
    'source_id': 'E2E-39',
    'preconditions': 'No matching supplier/item lookup or active Non-UNSPSC rule at the start. '
                     'Relevant corpus candidates available. Control each independent positive '
                     'selection to retrieved 43212105.',
    'expected': '1. The first three organisations independently select code 43212105, updating the '
                'same saved row.\n'
                ' 2. The agreement list contains one, then two, then three distinct organisations. '
                'The answer is organisation-specific after the first two and shared after the '
                'third (stable=false, false, then true).\n'
                ' 3. The fourth organisation receives STABLE_LOOKUP without running Identify, '
                'Search or Evaluation.',
    'mode': 'promotion',
    'code': '43212105'}

CASE = LiveCase(SPEC, ROOT / "performance" / "fixtures" / "039_fixture_share_an_answer_after_three_organisations_agree.jsonl")
