"""Generates a json file based on an Execution object."""

from typing import override

from src.notationparser.classes import Agent
from src.notationparser.execution.execution import ExecutionManager
from src.notationparser.json.json_creator import BeatInfo, JsonCreator
from src.settings.classes import PartForm, RunSettings


class JsonGeneratorAgent(Agent):
    """This Parser creates a JSON file based on a Score objects."""

    LOGGING_MESSAGE = "EXPORTING JSON FILE"
    EXPECTED_INPUT_TYPES = (Agent.InputOutputType.RUNSETTINGS, Agent.InputOutputType.EXECUTION)
    RETURN_TYPE = Agent.InputOutputType.PART

    part_info: PartForm = None
    exec_mgr: ExecutionManager = None

    def __init__(self, run_settings: RunSettings, execution: ExecutionManager):
        super().__init__(run_settings)
        self.exec_mgr = execution
        self.score = execution.score
        self.part_info = PartForm(
            part=self.run_settings.part_id,
            file=self.run_settings.midi_out_file,
            loop=self.run_settings.notation_settings.loop,
        )

    @override
    @classmethod
    def run_condition_satisfied(cls, run_settings: RunSettings):
        return run_settings.options.notation_to_midi and run_settings.options.notation_to_midi.save_jsonfile

    def _notation_to_dict(self) -> JsonCreator:
        """Generates the JSON content for the score object.

        Returns:
            JsonCreator: dict containing the score information.
        """

        json_dict = JsonCreator(run_settings=self.run_settings)

        json_dict.add_title(self.score.title)
        json_dict.add_composer("")

        self.exec_mgr.reset()

        # Select the first beat.
        beat = self.exec_mgr.next_beat_in_flow()
        temp = []
        flow = []
        while beat:
            if not temp or (beat.gongan_id != temp[-1].gongan_id) or (beat.id <= temp[-1].id):
                temp.append(beat)
                flow.append(beat.gongan_id)

            # Set new beat info.
            start_bpm, end_bpm = self.exec_mgr.get_tempo_values()
            velocities_dict = self.exec_mgr.get_dynamics_values()
            start_velocities = {pos: startval for pos, (startval, _) in velocities_dict.items()}
            end_velocities = {pos: endval for pos, (_, endval) in velocities_dict.items()}
            beat_info = BeatInfo(
                fullid=beat.full_id,
                start_bpm=start_bpm,
                end_bpm=end_bpm,
                start_velocities=start_velocities,
                end_velocities=end_velocities,
                duration=beat.duration,
            )
            json_dict.append_beat_info(beat, beat_info)

            beat = self.exec_mgr.next_beat_in_flow()

        return json_dict

    @override
    def _main(self) -> bool:
        """Generates the JSON content and saves it to file.

        Return:
            int: Total duration in milliseconds

        """
        # TODO Error handling and return False if error occurred
        score_dict = self._notation_to_dict()
        score_dict.save_to_json()
        self.logger.info("File saved as %s", self.run_settings.json_out_filepath)

        if self.has_errors:
            return False

        return True


if __name__ == "__main__":
    pass
