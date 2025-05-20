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
        pass

    def run_test_small(self, run_settings: RunSettings, notations: list[str]):
        """Tweaks the run settings do that only the tests in

        Args:
            run_settings (RunSettings): _description_
            notations (list[str]): _description_
        """
        for notation_id, notation in run_settings.configdata.notations.items():
            if notation_id in self.SMALL_TEST_NOTATIONS:
                notation.folder_out_nonprod = "./tests/data/notation/_integration_test_small/output"
                notation.include_in_run_types = [RunType.RUN_ALL]
            else:
                notation.include_in_run_types = []

    RUN_INTEGRATION_TEST = True  # <== SET TO True TO RUN THIS TEST (0.5 MIN. OR MORE RUNTIME)
    RUN_SMALL_TEST = False  # <== a small test will only run the given titles and save the results in "./tests/data/notation/_integration_test_small/output"
    SMALL_TEST_NOTATIONS = ["kahyangan"]

    @pytest.mark.skipif(RUN_INTEGRATION_TEST is False, reason="Set RUN_INTEGRATION_TEST=True to run the test")
    @unittest.skipIf(RUN_INTEGRATION_TEST is False, reason="Set RUN_INTEGRATION_TEST=True to run the test")
    def test_integrationtest(self):
        """
        NOTE: this test typically takes between 30 seconds and a minute to run if the test succeeds. However the
        duration can grow to several minutes if it fails.
        1. Runs the src.notation2midi.main.main() function for all notations marked RUN_ALL in
           tests/config/config.yaml and saves the MIDI files in the `data/notation/_integration_test/output` folder.
        2. Creates a text version of each MIDI file in the same folder.
        3. Compares these with the corresponding files in the `reference` folder and saves a report
           `comparison.txt` and `comparison details.txt` in the `output` folder.
        The content of file comparison.txt should be checked manually.
        """
        os.environ["GAMELAN_NOTATION_N2M_SETTINGS_PATH"] = "./tests/config/notation2midi_integration_test.yaml"
        # The dummy notation item `integration_test` in config.yaml contains the input and output folders
        # for the compare_all function.
        run_settings = Settings.get(
            notation_id="integration_test_small" if self.RUN_SMALL_TEST else "integration_test", part_id="dummy"
        )
        reference_dict = run_settings.notation.folder_in
        compare_dict = run_settings.folder_out
        run_settings.options.notation_to_midi.runtype = RunType.RUN_ALL
        if self.RUN_SMALL_TEST:
            self.run_test_small(run_settings=run_settings, notations=self.SMALL_TEST_NOTATIONS)
        main()  # Converts the notations whose setting `include_in_run_types` contains value RUN_ALL.
        no_differences = compare_all(ref_dir=reference_dict, other_dir=compare_dict)
        self.assertTrue(no_differences)
