"""Reset prior agreements when the classification changes."""
from importlib import import_module

from performance.e2e import CliScenario

setup = import_module("performance.setup.041_setup_reset_prior_agreements_when_the_classification_changes")


class Case041(CliScenario):
    case = setup.CASE
