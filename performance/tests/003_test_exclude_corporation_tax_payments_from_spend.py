"""Exclude corporation tax payments from spend."""
from importlib import import_module

from performance.e2e import RuleScenario

setup = import_module("performance.setup.003_setup_exclude_corporation_tax_payments_from_spend")


class Case003(RuleScenario):
    case = setup.CASE
