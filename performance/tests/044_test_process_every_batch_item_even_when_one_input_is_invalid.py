"""Process every batch item even when one input is invalid."""
from importlib import import_module

from performance.e2e import CliScenario

setup = import_module("performance.setup.044_setup_process_every_batch_item_even_when_one_input_is_invalid")


class Case044(CliScenario):
    case = setup.CASE
