"""Classify rebate management services instead of excluding them."""
from importlib import import_module

from performance.e2e import CliScenario

setup = import_module("performance.setup.024_setup_classify_rebate_management_services_instead_of_excluding_them")


class Case024(CliScenario):
    case = setup.CASE
