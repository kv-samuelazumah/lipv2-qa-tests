"""Reuse an organisation’s own saved cleaning classification."""
from importlib import import_module

from performance.e2e import CliScenario

setup = import_module("performance.setup.034_setup_reuse_an_organisation_s_own_saved_cleaning_classification")


class Case034(CliScenario):
    case = setup.CASE
