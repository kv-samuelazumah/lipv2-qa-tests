"""Share an answer after three organisations agree."""
from importlib import import_module

from performance.e2e import CliScenario

setup = import_module("performance.setup.039_setup_share_an_answer_after_three_organisations_agree")


class Case039(CliScenario):
    case = setup.CASE
