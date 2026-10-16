"""Exclude refunds from classification."""
from importlib import import_module

from performance.e2e import RuleScenario

setup = import_module("performance.setup.014_setup_exclude_refunds_from_classification")


class Case014(RuleScenario):
    case = setup.CASE
