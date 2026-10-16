"""Mark late payment interest for spend exclusion and review."""
from importlib import import_module

from performance.e2e import RuleScenario

setup = import_module("performance.setup.009_setup_mark_late_payment_interest_for_spend_exclusion_and_review")


class Case009(RuleScenario):
    case = setup.CASE
