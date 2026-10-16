"""Reuse the router classification when punctuation changes."""
from importlib import import_module

from performance.e2e import CliScenario

setup = import_module("performance.setup.028_setup_reuse_the_router_classification_when_punctuation_changes")


class Case028(CliScenario):
    case = setup.CASE
