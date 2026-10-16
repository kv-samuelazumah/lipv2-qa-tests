"""Leave an unclear adjustment unresolved."""
from importlib import import_module

from performance.e2e import CliScenario

setup = import_module("performance.setup.043_setup_leave_an_unclear_adjustment_unresolved")


class Case043(CliScenario):
    case = setup.CASE
