"""Mark rebate amounts for exclusion and review."""
from importlib import import_module

from performance.e2e import RuleScenario

setup = import_module("performance.setup.023_setup_mark_rebate_amounts_for_exclusion_and_review")


class Case023(RuleScenario):
    case = setup.CASE
