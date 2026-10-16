"""Share a saved classification with a new organisation."""
from importlib import import_module

from performance.e2e import CliScenario

setup = import_module("performance.setup.033_setup_share_a_saved_classification_with_a_new_organisation")


class Case033(CliScenario):
    case = setup.CASE
