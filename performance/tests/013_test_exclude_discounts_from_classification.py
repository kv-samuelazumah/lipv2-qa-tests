"""Exclude discounts from classification."""
from importlib import import_module

from performance.e2e import RuleScenario

setup = import_module("performance.setup.013_setup_exclude_discounts_from_classification")


class Case013(RuleScenario):
    case = setup.CASE
