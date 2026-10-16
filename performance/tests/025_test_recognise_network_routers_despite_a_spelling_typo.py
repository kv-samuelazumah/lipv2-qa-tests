"""Recognise network routers despite a spelling typo."""
from importlib import import_module

from performance.e2e import CliScenario

setup = import_module("performance.setup.025_setup_recognise_network_routers_despite_a_spelling_typo")


class Case025(CliScenario):
    case = setup.CASE
