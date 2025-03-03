import unittest
from unittest.mock import patch

from src.settings.settings import load_run_settings
from src.tools.compare import compare_all


class IntegrationTester(unittest.TestCase):
    """Integration tests, run separately."""

    def setUp(self):
        pass

    @patch("src.settings.settings.SETTINGSFOLDER", "./tests/settings")
    @patch("src.settings.settings.RUN_SETTINGSFILE", "notation2midi_integration_test.yaml")
    def test_integrationtest(self):
        run_settings = load_run_settings()
        # multiple_notations_to_midi(run_settings)
        compare_dict = run_settings.notation.folder_out
        reference_dict = compare_dict.replace("output", "reference")
        compare_all(reference_dict, compare_dict)
