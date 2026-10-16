"""Mark security deposits for spend exclusion and review."""
from importlib import import_module

from performance.e2e import RuleScenario

setup = import_module("performance.setup.010_setup_mark_security_deposits_for_spend_exclusion_and_review")


class Case010(RuleScenario):
    case = setup.CASE
