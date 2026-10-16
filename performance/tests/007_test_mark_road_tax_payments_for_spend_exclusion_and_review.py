"""Mark road tax payments for spend exclusion and review."""
from importlib import import_module

from performance.e2e import RuleScenario

setup = import_module("performance.setup.007_setup_mark_road_tax_payments_for_spend_exclusion_and_review")


class Case007(RuleScenario):
    case = setup.CASE
