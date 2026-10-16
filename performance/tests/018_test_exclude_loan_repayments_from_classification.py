"""Exclude loan repayments from classification."""
from importlib import import_module

from performance.e2e import RuleScenario

setup = import_module("performance.setup.018_setup_exclude_loan_repayments_from_classification")


class Case018(RuleScenario):
    case = setup.CASE
