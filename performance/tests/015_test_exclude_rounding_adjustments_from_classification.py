"""Exclude rounding adjustments from classification."""
from importlib import import_module

from performance.e2e import RuleScenario

setup = import_module("performance.setup.015_setup_exclude_rounding_adjustments_from_classification")


class Case015(RuleScenario):
    case = setup.CASE
