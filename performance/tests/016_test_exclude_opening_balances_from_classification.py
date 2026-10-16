"""Exclude opening balances from classification."""
from importlib import import_module

from performance.e2e import RuleScenario

setup = import_module("performance.setup.016_setup_exclude_opening_balances_from_classification")


class Case016(RuleScenario):
    case = setup.CASE
