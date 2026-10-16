"""Send penalties and fines for human review."""
from importlib import import_module

from performance.e2e import RuleScenario

setup = import_module("performance.setup.022_setup_send_penalties_and_fines_for_human_review")


class Case022(RuleScenario):
    case = setup.CASE
