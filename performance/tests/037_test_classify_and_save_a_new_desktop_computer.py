"""Classify and save a new desktop computer."""
from importlib import import_module

from performance.e2e import CliScenario

setup = import_module("performance.setup.037_setup_classify_and_save_a_new_desktop_computer")


class Case037(CliScenario):
    case = setup.CASE
