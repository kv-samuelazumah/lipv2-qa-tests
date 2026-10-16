"""Recognise “late interest payment” as a late payment charge."""
from importlib import import_module

from performance.e2e import RuleScenario

setup = import_module("performance.setup.011_setup_recognise_late_interest_payment_as_a_late_payment_charge")


class Case011(RuleScenario):
    case = setup.CASE
