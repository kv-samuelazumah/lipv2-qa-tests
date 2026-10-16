"""Keep an organisation-specific answer private to that organisation."""
from importlib import import_module

from performance.e2e import CliScenario

setup = import_module("performance.setup.035_setup_keep_an_organisation_specific_answer_private_to_that_organisation")


class Case035(CliScenario):
    case = setup.CASE
