import os
import unittest

import pytest

from src.notation2midi.main import main
from src.settings.classes import RunSettings, RunType
from src.settings.settings import Settings
from src.tools.compare import compare_all
from tests.conftest import BaseUnitTestCase


class IntegrationTester(BaseUnitTestCase):
    """Integration tests, run separately."""

    def setUp(self):
        os.environ["GAMELAN_NOTATION_N2M_SETTINGS_PATH"] = "./tests/config/notation2midi_integration_test.yaml"

    def clear_small_test_output_folder(self, run_settings: RunSettings):
        """Removes previous output from the small test output folder"""
        # Remove existing content from the output file
        for filename in os.listdir(run_settings.folder_out):
            file_path = os.path.join(run_settings.folder_out, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)

    #######################################################################################################################################################
    RUN_INTEGRATION_TEST = False  # <== SET TO True TO RUN THIS TEST (0.5 MIN. OR MORE RUNTIME)
    RUN_SMALL_TEST = False  # <== a small test will only run the given titles and save the results in "./tests/data/notation/_integration_test_small/output"
    SMALL_TEST_NOTATION_ID = "gilak deng"
    #######################################################################################################################################################

    @pytest.mark.skipif(RUN_INTEGRATION_TEST is False, reason="Set RUN_INTEGRATION_TEST=True to run the test")
    @unittest.skipIf(RUN_INTEGRATION_TEST is False, reason="Set RUN_INTEGRATION_TEST=True to run the test")
    def test_integrationtest(self):
        """
        NOTE: this test typically takes between 30 seconds and a minute to run if the test succeeds. However the
        duration can increase to several minutes if the test fails.
        1. Runs the src.notation2midi.main.main() function for all notations marked RUN_ALL in
           tests/config/config.yaml and saves the MIDI files in the `data/notation/_integration_test/output` folder.
        2. Creates a text version of each MIDI file in the same folder.
        3. Compares these with the corresponding files in the `reference` folder and saves a report
           `comparison.txt` and `comparison details.txt` in the `output` folder.
        The content of file comparison.txt should be checked manually.
        """
        run_settings = Settings.get()
        if self.RUN_SMALL_TEST:
            run_settings = Settings.get(notation_id=self.SMALL_TEST_NOTATION_ID, part_id="full")
            run_settings.options.notation_to_midi.run_type = RunType.INTEGRATION_TEST_SMALL
            self.clear_small_test_output_folder(run_settings)
        else:
            run_settings.options.notation_to_midi.run_type = RunType.INTEGRATION_TEST
        test_reference_dir = run_settings.configdata.unittest.folder_reference_integration_test
        compare_dir = run_settings.folder_out
        main()  # Converts the notations whose setting `include_in_run_types` contains value RUN_ALL.
        no_differences = compare_all(ref_dir=test_reference_dir, other_dir=compare_dir)
        self.assertTrue(no_differences)
