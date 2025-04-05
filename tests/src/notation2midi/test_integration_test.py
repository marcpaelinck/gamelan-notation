import os

import pytest

from src.notation2midi.main import main
from src.settings.classes import RunType
from src.settings.settings import Settings
from src.tools.compare import compare_all
from tests.conftest import BaseUnitTestCase


class IntegrationTester(BaseUnitTestCase):
    """Integration tests, run separately."""

    def setUp(self):
        pass

    RUN_INTEGRATION_TEST = True  # <== SET TO True TO RUN THIS TEST (~ 1 MIN. RUNTIME)

    @pytest.mark.skipif(RUN_INTEGRATION_TEST is False, reason="Set RUN_INTEGRATION_TEST=True to run the test")
    def test_integrationtest(self):
        """
        NOTE: this test might take over a minute to run.
        1. Runs the src.notation2midi.main.main() function for all notations marked RUN_ALL in
           tests/settings/config.yaml and saves the MIDI files in the `data/notation/_integration_test/output` folder.
        2. Creates a text version of each MIDI file in the same folder.
        3. Compares these with the corresponding files in the `reference` folder and saves a report
           `comparison.txt` and `comparison details.txt` in the `output` folder."""
        os.environ["GAMELAN_NOTATION_N2M_SETTINGS_PATH"] = "./tests/settings/notation2midi_integration_test.yaml"
        # The dummy notation item `integration_test` in config.yaml contains the input and output folders
        # for the compare_all function.
        run_settings = Settings.get(notation_id="integration_test", part_id="dummy")
        reference_dict = run_settings.notation.folder_in
        compare_dict = run_settings.folder_out
        run_settings.options.notation_to_midi.runtype = RunType.RUN_ALL
        main()
        compare_all(ref_dir=reference_dict, other_dir=compare_dict)
