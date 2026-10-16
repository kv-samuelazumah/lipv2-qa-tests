"""Send service charges for human review."""
from importlib import import_module

from performance.e2e import RuleScenario

setup = import_module("performance.setup.021_setup_send_service_charges_for_human_review")


class Case021(RuleScenario):
    case = setup.CASE
