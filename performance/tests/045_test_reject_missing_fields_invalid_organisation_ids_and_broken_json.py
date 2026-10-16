"""Reject missing fields, invalid organisation IDs and broken JSON."""
from importlib import import_module

from performance.e2e import CliScenario

setup = import_module("performance.setup.045_setup_reject_missing_fields_invalid_organisation_ids_and_broken_json")


class Case045(CliScenario):
    case = setup.CASE
