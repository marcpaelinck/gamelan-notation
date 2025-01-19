import os
import pprint

from mido import MidiFile

from src.common.classes import Beat, Preset, Score
from src.common.constants import DEFAULT, Pitch, Position
from src.common.metadata_classes import PartMeta
from src.notation2midi.classes import ParserModel
from src.notation2midi.midi_track import MidiTrackX, TimeUnit
from src.settings.classes import Part, RunSettings, Song
from src.settings.settings import (
    get_midiplayer_content,
    get_run_settings,
    save_midiplayer_content,
)


class MidiGenerator(ParserModel):

    player_data: Part = None

    def __init__(self, score: Score):
        super().__init__(self.ParserType.MIDIGENERATOR, score.settings)
        self.score = score
        self.player_data = Part(
            part=self.run_settings.notation.part.name,
            file=self.run_settings.notation.midi_out_file,
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
                if self.player_data.markers.get(partinfo.name, None):
                    # Return if the part has already been registered
                    return
                curr_time = track.current_time_in_millis()
                self.player_data.markers[partinfo.name] = int(curr_time)

        track = MidiTrackX(position, Preset.get_preset(position), self.run_settings)
        # Add silence before the start of the piece, except if the piece should be played in a loop.
        if not self.run_settings.notation.part.loop:
            track.increase_current_time(self.run_settings.midi.silence_seconds_before_start, TimeUnit.SECOND)

        reset_pass_counters()
        beat = self.score.gongans[0].beats[0]
        while beat:
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
                beat = beat.repeat.goto
            else:
                if beat.repeat:
                    beat.repeat.reset()
                beat = beat.goto.get(beat._pass_, beat.next)

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

    def update_midiplayer_content(self) -> None:
        content = get_midiplayer_content()
        # If info is already present, replace it.
        song = next((song for song in content.songs if song.title == self.score.title), None)
        if not song:
            # TODO create components of Song
            content.songs.append(
                song := Song(
                    title=self.run_settings.notation.title,
                    display=True,
                    instrumentgroup=self.run_settings.instruments.instrumentgroup,
                )
            )
            self.loginfo(f"New song {song.title} created for MIDI player content")
        part = next((part for part in song.parts if part.part == self.player_data.part), None)
        if not part:
            song.parts.append(
                part := Part(
                    part=self.player_data.part,
                    file=self.player_data.file,
                    loop=self.player_data.loop,
                )
            )
            self.loginfo(f"New part {part.part} created for MIDI player content")
        else:
            self.loginfo(f"Existing part {part.part} updated for MIDI player content")
            part.file = self.player_data.file
            part.loop = self.player_data.loop
        part.markers = self.sorted_markers_millis_to_frac(self.player_data.markers, self.score.midifile_duration)
        self.loginfo(f"Added time markers to part {part.part}")
        save_midiplayer_content(content)

    def create_midifile(self):
        """Generates the MIDI content and saves it to file.

        Return:
            int: Total duration in milliseconds

        """
        midifile = MidiFile(ticks_per_beat=self.run_settings.midi.PPQ, type=1)

        for position in sorted(self.score.instrument_positions, key=lambda x: x.sequence):
            track = self._notation_to_track(position)
            midifile.tracks.append(track)
        if not self.run_settings.notation.part.loop:
            self._add_attenuation_time(midifile.tracks, seconds=self.run_settings.midi.silence_seconds_after_end)
        self.score.midifile_duration = int(midifile.length * 1000)

        if self.run_settings.options.notation_to_midi.save_midifile:
            is_test_file = self.run_settings.notation.part.file.lower().startswith(
                "test"
            ) or self.run_settings.notation.folder.lower().endswith("test")
            if self.run_settings.options.notation_to_midi.update_midiplayer_content and not is_test_file:
                # Test files should not be saved to the midiplayer folder
                outfilepath = self.run_settings.notation.midi_out_filepath_midiplayer
            else:
                outfilepath = self.run_settings.notation.midi_out_filepath
            midifile.save(outfilepath)
            self.logger.info(f"File saved as {outfilepath}")

            if self.run_settings.options.notation_to_midi.update_midiplayer_content and not is_test_file:
                # Test files should never be logged in the midiplayer content file
                self.update_midiplayer_content()

        self.logger.info("=====================================")


if __name__ == "__main__":
    run_settings = get_run_settings()
    content = get_midiplayer_content()
    str_content = content.model_dump_json(indent=4, serialize_as_any=True)
    datafolder = run_settings.notation.folder
    content_json = content.model_dump_json(indent=4, serialize_as_any=True)
    with open(os.path.join(datafolder, "content_test.json"), "w") as contentfile:
        pprint.pprint(content_json, stream=contentfile, width=250)
