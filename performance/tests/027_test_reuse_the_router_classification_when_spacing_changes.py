"""Reuse the router classification when spacing changes."""
from importlib import import_module

from performance.e2e import CliScenario

setup = import_module("performance.setup.027_setup_reuse_the_router_classification_when_spacing_changes")


class Case027(CliScenario):
    case = setup.CASE
