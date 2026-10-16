"""Mark parking penalty notices for spend exclusion and review."""
from importlib import import_module

from performance.e2e import RuleScenario

setup = import_module("performance.setup.008_setup_mark_parking_penalty_notices_for_spend_exclusion_and_review")


class Case008(RuleScenario):
    case = setup.CASE
