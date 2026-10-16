"""Classify toner as a consumable rather than a printer."""
from importlib import import_module

from performance.e2e import CliScenario

setup = import_module("performance.setup.042_setup_classify_toner_as_a_consumable_rather_than_a_printer")


class Case042(CliScenario):
    case = setup.CASE
