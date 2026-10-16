"""Reuse the saved desktop computer classification."""
from importlib import import_module

from performance.e2e import CliScenario

setup = import_module("performance.setup.038_setup_reuse_the_saved_desktop_computer_classification")


class Case038(CliScenario):
    case = setup.CASE
