"""Use a saved classification before a conflicting exclusion rule."""
from importlib import import_module

from performance.e2e import CliScenario

setup = import_module("performance.setup.036_setup_use_a_saved_classification_before_a_conflicting_exclusion_rule_stable")


class Case036(CliScenario):
    case = setup.CASE
