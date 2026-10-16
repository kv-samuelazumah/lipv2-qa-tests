"""Send donations for human review."""
from importlib import import_module

from performance.e2e import RuleScenario

setup = import_module("performance.setup.020_setup_send_donations_for_human_review")


class Case020(RuleScenario):
    case = setup.CASE
