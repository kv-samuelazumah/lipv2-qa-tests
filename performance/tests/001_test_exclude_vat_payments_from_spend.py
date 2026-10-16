"""Exclude VAT payments from spend."""
from importlib import import_module

from performance.e2e import RuleScenario

setup = import_module("performance.setup.001_setup_exclude_vat_payments_from_spend")


class Case001(RuleScenario):
    case = setup.CASE
