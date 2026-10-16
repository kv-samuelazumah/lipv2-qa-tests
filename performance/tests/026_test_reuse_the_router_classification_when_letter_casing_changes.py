"""Reuse the router classification when letter casing changes."""
from importlib import import_module

from performance.e2e import CliScenario

setup = import_module("performance.setup.026_setup_reuse_the_router_classification_when_letter_casing_changes")


class Case026(CliScenario):
    case = setup.CASE
