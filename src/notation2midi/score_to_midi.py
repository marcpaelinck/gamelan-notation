"""Generates a midi file based on a Score object.
Keeps track of the number of time each beat was passed and processes the flow (GOTOs, SEQUENCEs, REPEATs) accordingly.
Main method: create_midifile()
"""

import sys
from typing import override

from mido import MidiFile

from src.common.classes import Beat, Preset
from src.common.constants import DEFAULT, Pitch, Position
from src.notation2midi.classes import Agent
from src.notation2midi.execution import ExecutionManager, Score
from src.notation2midi.metadata_classes import PartMeta
from src.notation2midi.midi_track import MidiTrackX, TimeUnit
from src.settings.classes import PartForm, RunSettings


class MidiGeneratorAgent(Agent):
    """This Parser creates a MIDI file based on a Score objects."""

    AGENT_TYPE = Agent.AgentType.MIDIGENERATOR
    EXPECTED_INPUT_TYPES = (Agent.InputOutputType.RUNSETTINGS, Agent.InputOutputType.SCORE)
    RETURN_TYPE = Agent.InputOutputType.PART

    part_info: PartForm = None
    exec_mgr: ExecutionManager = None

    def __init__(self, run_settings: RunSettings, score: Score):
        super().__init__(run_settings)
        self.score = score
        self.exec_mgr = self.score.execution_manager
        self.part_info = PartForm(
            part=self.run_settings.notation.part.name,
            file=self.run_settings.midi_out_file,
            loop=self.run_settings.notation.part.loop,
        )

    @override
    @classmethod
    def run_condition_satisfied(cls, run_settings: RunSettings):
        return run_settings.options.notation_to_midi and run_settings.options.notation_to_midi.save_midifile

    def _add_attenuation_time(self, tracks: list[MidiTrackX], seconds: int) -> None:
        """Extends the duration of the final note in each channel to avoid an abrupt ending of the audio.

        Args:
            tracks (list[MidiTrackX]): Tracks for which to extend the last note.
            seconds (int): Duration of the extension.
        """
        max_ticks = max(track.total_tick_time() for track in tracks)
        for track in tracks:
            if track.total_tick_time() == max_ticks:
                track.extend_last_notes(seconds, TimeUnit.SECOND)

    def _notation_to_track(self, position: Position) -> MidiTrackX:
        """Generates the MIDI content for a single instrument position.

        Args:
            score (Score): The object model containing the notation.
            position (Position): the instrument position

        Returns:
            MidiTrack: MIDI track for the instrument.
        """

        def reset_pass_counters():
            self.exec_mgr.reset_all_counters()

        def store_part_info(beat: Beat):
            # current_time_in_millis might be incorrect if the beat consists of only silences.
            if all(note.pitch == Pitch.NONE for note in beat.get_notes(position, DEFAULT)):
                return
            gongan = self.score.gongans[beat.gongan_seq]
            if partinfo := gongan.get_metadata(PartMeta):
                if self.part_info.markers.get(partinfo.name, None):
                    # Return if the part has already been registered
                    return
                # curr_time = track.current_time_in_millis()
                curr_time = track.current_millitime
                self.part_info.markers[partinfo.name] = int(curr_time)

        track = MidiTrackX(position, Preset.get_preset(position), self.run_settings)
        # Add silence before the start of the piece, except if the piece should be played in a loop.
        if not self.run_settings.notation.part.loop:
            track.increase_current_time(self.run_settings.midi.silence_seconds_before_start, TimeUnit.SECOND)

        reset_pass_counters()
        # Temporary fix: create a dummy beat as starting point for the execution.
        # This enables to call self.exec_mgr.next_beat_in_flow(beat) to select the first beat.
        # This updates all execution values correctly.
        beat = Beat(
            id=0,
            gongan_id=0,
            duration=0,
            next=self.score.gongans[0].beats[0],
        )
        # Select the first beat.
        beat = self.exec_mgr.next_beat_in_flow(beat)
        # beat = self.score.gongans[0].beats[0]
        temp = []
        flow = []
        while beat:
            if not temp or (beat.gongan_id != temp[-1].gongan_id) or (beat.id <= temp[-1].id):
                temp.append(beat)
                flow.append(beat.gongan_id)
            # self.loginfo(f"beat={beat.full_id}")
            # Add a marker with the beat full_id for easier debugging when running the integration test.
            if self.run_settings.options.notation_to_midi.is_integration_test:
                track.marker(f"b_{beat.full_id}")
            # If a new part is encountered, store timestamp and name in the midiplayer_data section of the score
            store_part_info(beat)
            # beat.flow.incr_pass_counter(Flow.FlowType.GOTO)
            if self.run_settings.options.debug_logging:
                track.comment(
                    f"beat {beat.full_id} pass{self.exec_mgr.goto(beat).counter} "
                    f"loop{self.exec_mgr.loop(beat).counter if self.exec_mgr.loop(beat) else "-"}"
                )
            # Set new tempo.
            if new_bpm := self.exec_mgr.get_tempo(beat=beat, curr_tempo=track.current_bpm):
                track.update_tempo(new_bpm)
            # Set new dynamics
            if new_velocity := self.exec_mgr.get_dynamics(
                beat=beat, position=position, curr_dynamics=track.current_velocity
            ):
                track.update_dynamics(new_velocity)

            # Process individual notes.
            try:
                # TODO: create function Beat.next_beat_in_flow()
                if self.exec_mgr.goto(beat):
                    pass_ = beat.measures[position].passes.get(
                        self.exec_mgr.goto(beat).counter, beat.measures[position].passes[DEFAULT]
                    )
                else:
                    pass_ = beat.measures[position].passes[DEFAULT]
            except KeyError:
                self.logerror(f"No measure found for {position} in beat {beat.full_id}. Program halted.")
                sys.exit()
            for note in pass_.notes:
                track.add_note(note)
            beat = self.exec_mgr.next_beat_in_flow(beat)
            # TODO GOTO modify, also for freq type

        track.finalize()
        if position == Position.PEMADE_POLOS:
            self.loginfo(f"{flow=}")

        return track

    def sorted_markers_millis_to_frac(self, markers: dict[str, int], total_duration: int) -> dict[str, float]:
        """Converts the markers that indicate the start of parts of the composition from milliseconds to
        percentage of the total duration (rounded off to 5%)
        The list needs to be sorted chronologically for the user interface of the midi player.

        Args:
            dict: a dict

        Returns:
            dict: a new markers dict
        """
        return {part: time / total_duration for part, time in sorted(list(markers.items()), key=lambda it: it[1])}

    def _get_part_info(self) -> None:
        return PartForm(
            part=self.part_info.part,
            file=self.part_info.file,
            loop=self.part_info.loop,
            markers=self.sorted_markers_millis_to_frac(self.part_info.markers, self.score.midifile_duration),
        )

    @override
    def _main(self) -> PartForm:
        """Generates the MIDI content and saves it to file.

        Return:
            int: Total duration in milliseconds

        """
        # TODO Error handling and return False if error occurred
        midifile = MidiFile(ticks_per_beat=self.run_settings.midi.PPQ, type=1)

        for position in sorted(self.score.instrument_positions, key=lambda x: x.sequence):
            track = self._notation_to_track(position)
            midifile.tracks.append(track)
        if not self.run_settings.notation.part.loop:
            self._add_attenuation_time(midifile.tracks, seconds=self.run_settings.midi.silence_seconds_after_end)
        self.score.midifile_duration = int(midifile.length * 1000)

        midifile.save(self.run_settings.midi_out_filepath)
        self.logger.info("File saved as %s", self.run_settings.midi_out_filepath)

        if self.has_errors:
            return None

        return self._get_part_info()


if __name__ == "__main__":
    pass
