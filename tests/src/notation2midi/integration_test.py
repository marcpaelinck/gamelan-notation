import os
import unittest

from src.settings.settings import load_run_settings
from src.tools.compare import compare_all


class IntegrationTester(unittest.TestCase):
    """Integration tests, run separately."""

    def setUp(self):
        pass

    # Perform a run with RUN_ALL before
    def test_integrationtest(self):
        run_settings = load_run_settings(notation_id="integration_test", part_id="dummy")
        compare_dict = run_settings.folder_out
        reference_dict = run_settings.notation.folder_in
        compare_all(reference_dict, compare_dict)
