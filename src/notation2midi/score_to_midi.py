import os
import pprint

from mido import MidiFile

from src.common.classes import Beat, Preset, Score
from src.common.constants import DEFAULT, Pitch, Position
from src.common.metadata_classes import PartMeta
from src.notation2midi.classes import ParserModel
from src.notation2midi.midi_track import MidiTrackX, TimeUnit
from src.settings.classes import PartForm
from src.settings.settings import (
    get_midiplayer_content,
    get_run_settings,
    update_midiplayer_content,
)


class MidiGenerator(ParserModel):

    part_info: PartForm = None

    def __init__(self, score: Score):
        super().__init__(self.ParserType.MIDIGENERATOR, score.settings)
        self.score = score
        self.part_info = PartForm(
            part=self.run_settings.notation.part.name,
            file=self.run_settings.notation.midi_out_file,
            pdf=self.run_settings.notation.pdf_out_file,
            loop=self.run_settings.notation.part.loop,
        )

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
            for gongan in self.score.gongans:
                for beat in gongan.beats:
                    beat._pass_ = 0
                    if beat.repeat:
                        beat.repeat.reset()

        def store_part_info(beat: Beat):
            # current_time_in_millis might be incorrect if the beat consists of only silences.
            if all(note.pitch == Pitch.NONE for note in beat.get_notes(position, DEFAULT)):
                return
            gongan = self.score.gongans[beat.gongan_seq]
            if partinfo := gongan.get_metadata(PartMeta):
                if self.part_info.markers.get(partinfo.name, None):
                    # Return if the part has already been registered
                    return
                curr_time = track.current_time_in_millis()
                self.part_info.markers[partinfo.name] = int(curr_time)

        track = MidiTrackX(position, Preset.get_preset(position), self.run_settings)
        # Add silence before the start of the piece, except if the piece should be played in a loop.
        if not self.run_settings.notation.part.loop:
            track.increase_current_time(self.run_settings.midi.silence_seconds_before_start, TimeUnit.SECOND)

        reset_pass_counters()
        beat = self.score.gongans[0].beats[0]
        while beat:
            # Add a marker with the beat full_id for easier debugging when running the integration test.
            if self.run_settings.options.notation_to_midi.is_integration_test:
                track.marker(f"b_{beat.full_id}")
            # If a new part is encountered, store timestamp and name in the midiplayer_data section of the score
            store_part_info(beat)
            beat._pass_ += 1
            if self.run_settings.options.debug_logging:
                track.comment(f"beat {beat.full_id} pass{beat._pass_}")
            # Set new tempo
            if new_bpm := beat.get_changed_value(track.current_bpm, position, Beat.Change.Type.TEMPO):
                track.update_tempo(new_bpm or beat.get_bpm_start())
            # Set new dynamics
            if new_velocity := beat.get_changed_value(track.current_velocity, position, Beat.Change.Type.DYNAMICS):
                track.update_dynamics(new_velocity or beat.get_velocity_start(position))

            # Process individual notes.
            try:
                pass_ = beat.measures[position].passes.get(beat._pass_, beat.measures[position].passes[DEFAULT])
            except:
                self.logerror(f"No score found for {position} in beat {beat.full_id}. Program halted.")
                exit()
            for note in pass_.notes:
                track.add_note(note)
            if beat.repeat and beat.repeat._countdown > 0:
                beat.repeat._countdown -= 1
                beat = beat.repeat.goto  # TODO GOTO modify, also for freq type
            else:
                if beat.repeat:
                    beat.repeat.reset()
                beat = beat.goto.get(
                    beat._pass_, beat.goto.get(DEFAULT, beat.next)
                )  # TODO GOTO modify, also for freq type

        track.finalize()

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

    def _update_midiplayer_content(self) -> None:
        update_midiplayer_content(
            title=self.run_settings.notation.title,
            group=self.run_settings.notation.instrumentgroup,
            partinfo=PartForm(
                part=self.part_info.part,
                file=self.part_info.file,
                pdf=None,
                loop=self.part_info.loop,
                markers=self.sorted_markers_millis_to_frac(self.part_info.markers, self.score.midifile_duration),
            ),
        )

    @ParserModel.main
    def create_midifile(self) -> bool:
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

        if self.run_settings.options.notation_to_midi.save_midifile:
            midifile.save(self.run_settings.notation.midi_out_filepath)
            self.logger.info(f"File saved as {self.run_settings.notation.midi_out_filepath}")

            if (
                self.run_settings.options.notation_to_midi.update_midiplayer_content
                and self.run_settings.notation.production
            ):
                # Test files should never be logged in the midiplayer content file
                self._update_midiplayer_content()

        return True


if __name__ == "__main__":
    run_settings = get_run_settings()
    content = get_midiplayer_content()
    str_content = content.model_dump_json(indent=4, serialize_as_any=True)
    datafolder = run_settings.notation.folder
    content_json = content.model_dump_json(indent=4, serialize_as_any=True)
    with open(os.path.join(datafolder, "content_test.json"), "w") as contentfile:
        pprint.pprint(content_json, stream=contentfile, width=250)
