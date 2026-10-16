"""Mark tips for spend exclusion and review."""
from importlib import import_module

from performance.e2e import RuleScenario

setup = import_module("performance.setup.012_setup_mark_tips_for_spend_exclusion_and_review")


class Case012(RuleScenario):
    case = setup.CASE
