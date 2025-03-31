import os
import unittest

import pytest

from src.notation2midi.main import main
from src.settings.classes import RunType
from src.settings.settings import load_run_settings
from src.tools.compare import compare_all


class IntegrationTester(unittest.TestCase):
    """Integration tests, run separately."""

    def setUp(self):
        pass

    RUN_INTEGRATION_TEST = False

    @pytest.mark.skipif(RUN_INTEGRATION_TEST is False, reason="Set RUN_INTEGRATION_TEST=True to run the test")
    def test_integrationtest(self):
        """
        NOTE: this test will take one to several minutes to run.
        1. Runs the main() function for all notations marked RUN_ALL in config.yaml
           and saves the MIDI files in the `data/notation/_integration_test/output` folder.
        2. Creates a text version of each MIDI file in the same folder.
        3. Compares these with the corresponding files in the `reference` folder and saves
           a report `comparison.txt` in the `output` folder."""
        # TODO improve the output to make the results easier to interpret.
        os.environ["GAMELAN_NOTATION_N2M_SETTINGS_PATH"] = "./tests/settings/notation2midi_integration_test.yaml"
        run_settings = load_run_settings(notation_id="integration_test", part_id="dummy")
        run_settings.options.notation_to_midi.runtype = RunType.RUN_ALL
        main()
        # The dummy notation `integration_test` contains the input and output folders for the compare_all function.
        reference_dict = run_settings.notation.folder_in
        compare_dict = run_settings.folder_out
        compare_all(ref_dir=reference_dict, other_dir=compare_dict)
