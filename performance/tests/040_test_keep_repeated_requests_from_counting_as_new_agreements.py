"""Keep repeated requests from counting as new agreements."""
from importlib import import_module

from performance.e2e import CliScenario

setup = import_module("performance.setup.040_setup_keep_repeated_requests_from_counting_as_new_agreements")


class Case040(CliScenario):
    case = setup.CASE
