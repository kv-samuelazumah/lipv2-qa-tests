"""Exclude PAYE payroll tax payments from spend."""
from importlib import import_module

from performance.e2e import RuleScenario

setup = import_module("performance.setup.002_setup_exclude_paye_payroll_tax_payments_from_spend")


class Case002(RuleScenario):
    case = setup.CASE
