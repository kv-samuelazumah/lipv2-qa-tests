"""Mark HMRC tax penalties for spend exclusion and review."""
from importlib import import_module

from performance.e2e import RuleScenario

setup = import_module("performance.setup.006_setup_mark_hmrc_tax_penalties_for_spend_exclusion_and_review")


class Case006(RuleScenario):
    case = setup.CASE
