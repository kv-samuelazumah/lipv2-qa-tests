"""Reject empty, null and missing descriptions."""
from importlib import import_module

from performance.e2e import CliScenario

setup = import_module("performance.setup.030_setup_reject_empty_null_and_missing_descriptions")


class Case030(CliScenario):
    case = setup.CASE
