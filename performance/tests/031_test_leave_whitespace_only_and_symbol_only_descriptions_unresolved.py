"""Leave whitespace-only and symbol-only descriptions unresolved."""
from importlib import import_module

from performance.e2e import CliScenario

setup = import_module("performance.setup.031_setup_leave_whitespace_only_and_symbol_only_descriptions_unresolved")


class Case031(CliScenario):
    case = setup.CASE
