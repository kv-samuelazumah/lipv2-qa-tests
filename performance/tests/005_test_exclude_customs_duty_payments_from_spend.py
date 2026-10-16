"""Exclude customs duty payments from spend."""
from importlib import import_module

from performance.e2e import RuleScenario

setup = import_module("performance.setup.005_setup_exclude_customs_duty_payments_from_spend")


class Case005(RuleScenario):
    case = setup.CASE
