"""Send ULEZ charges for human review."""
from importlib import import_module

from performance.e2e import RuleScenario

setup = import_module("performance.setup.019_setup_send_ulez_charges_for_human_review")


class Case019(RuleScenario):
    case = setup.CASE
