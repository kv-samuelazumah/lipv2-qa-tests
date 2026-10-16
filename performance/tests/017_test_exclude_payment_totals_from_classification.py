"""Exclude payment totals from classification."""
from importlib import import_module

from performance.e2e import RuleScenario

setup = import_module("performance.setup.017_setup_exclude_payment_totals_from_classification")


class Case017(RuleScenario):
    case = setup.CASE
