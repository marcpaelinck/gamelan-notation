import unittest
from unittest.mock import patch

from src.notation2midi.main import multiple_notations_to_midi
from src.settings.settings import load_run_settings


class IntegrationTester(unittest.TestCase):

    def setUp(self):
        pass

    @patch("src.settings.settings.SETTINGSFOLDER", "./tests/settings")
    @patch("src.settings.settings.RUN_SETTINGSFILE", "notation2midi_integration_test.yaml")
    def test_integrationtest(self):
        run_settings = load_run_settings()
        multiple_notations_to_midi(run_settings)
