"""Reuse the saved classification for Network_routers."""
from importlib import import_module

from performance.e2e import CliScenario

setup = import_module("performance.setup.029_setup_reuse_the_saved_classification_for_network_routers")


class Case029(CliScenario):
    case = setup.CASE
