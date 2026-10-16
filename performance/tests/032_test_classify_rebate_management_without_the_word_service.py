"""Classify rebate management without the word “service”."""
from importlib import import_module

from performance.e2e import CliScenario

setup = import_module("performance.setup.032_setup_classify_rebate_management_without_the_word_service")


class Case032(CliScenario):
    case = setup.CASE
