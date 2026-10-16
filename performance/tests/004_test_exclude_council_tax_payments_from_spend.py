"""Exclude council tax payments from spend."""
from importlib import import_module

from performance.e2e import RuleScenario

setup = import_module("performance.setup.004_setup_exclude_council_tax_payments_from_spend")


class Case004(RuleScenario):
    case = setup.CASE
