from mido import MidiFile

from src.common.classes import Beat, ParserModel, Score
from src.common.constants import InstrumentPosition
from src.common.lookups import LOOKUP
from src.common.metadata_classes import PartMeta
from src.common.playercontent_classes import Part, Song
from src.notation2midi.midi_track import MidiTrackX
from src.settings.settings import (
    ATTENUATION_SECONDS_AFTER_MUSIC_END,
    get_midiplayer_content,
    save_midiplayer_content,
)


class MidiGenerator(ParserModel):

    def __init__(self, score: Score):
        super().__init__(self.ParserType.MIDIGENERATOR, score.settings)
        self.score = score

    def _add_attenuation_time(self, tracks: list[MidiTrackX], seconds: int) -> None:
        """Extends the duration of the final note in each channel to avoid an abrupt ending of the audio.

        Args:
            tracks (list[MidiTrackX]): Tracks for which to extend the last note.
            seconds (int): Duration of the extension.
        """
        max_ticks = max(track.total_tick_time() for track in tracks)
        for track in tracks:
            if track.total_tick_time() == max_ticks:
                track.extend_last_note(seconds)

    def _notation_to_track(self, position: InstrumentPosition) -> MidiTrackX:
        """Generates the MIDI content for a single instrument position.

        Args:
            score (Score): The object model containing the notation.
            position (InstrumentPosition): the instrument position

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
            gongan = self.score.gongans[beat.sys_seq]
            if partinfo := gongan.get_metadata(PartMeta):
                curr_time = track.current_time_in_millis()
                # check if part was already set by another trach
                time = self.score.midiplayer_data.markers.get(partinfo.name)
                if time and time < curr_time:
                    # keep the earliest time
                    return
                self.score.midiplayer_data.markers[partinfo.name] = int(curr_time)

        track = MidiTrackX(position, LOOKUP.INSTRUMENT_TO_PRESET[position], self.run_settings.midi.PPQ)

        reset_pass_counters()
        beat = self.score.gongans[0].beats[0]
        while beat:
            # If a new part is encountered, store timestamp and name in the midiplayer_data section of the score
            store_part_info(beat)
            beat._pass_ += 1
            if self.run_settings.options.debug_logging:
                track.comment(f"beat {beat.full_id} pass{beat._pass_}")
            # Set new tempo
            if new_bpm := beat.get_changed_tempo(track.current_bpm):
                track.update_tempo(new_bpm or beat.get_bpm_start())

            # Process individual notes. Check if there is an alternative stave for the current pass
            for note in beat.exceptions.get((position, beat._pass_), beat.staves.get(position, [])):
                track.add_note(position, note)
            if beat.repeat and beat.repeat._countdown > 0:
                beat.repeat._countdown -= 1
                beat = beat.repeat.goto
            else:
                if beat.repeat:
                    beat.repeat.reset()
                beat = beat.goto.get(beat._pass_, beat.next)

        return track

    def markers_millis_to_frac(self, markers: dict[str, int], total_duration: int) -> dict[str, float]:
        """Converts the markers that indicate the start of parts of the composition from milliseconds to
        percentage of the total duration (rounded off to 5%)

        Args:
            dict: a dict

        Returns:
            dict: a new markers dict
        """
        return {part: time / total_duration for part, time in markers.items()}

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
        part = next((part for part in song.parts if part.name == self.score.midiplayer_data.name), None)
        if not part:
            song.parts.append(
                part := Part(
                    name=self.score.midiplayer_data.name,
                    file=self.score.midiplayer_data.file,
                    loop=self.score.midiplayer_data.loop,
                )
            )
            self.loginfo(f"New part {part.name} created for MIDI player content")
        else:
            self.loginfo(f"Existing part {part.name} updated for MIDI player content")
            part.file = self.score.midiplayer_data.file
            part.loop = self.score.midiplayer_data.loop
        part.markers = self.markers_millis_to_frac(self.score.midiplayer_data.markers, self.score.total_duration)
        self.loginfo(f"Added time markers to part {part.name}")
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
            self._add_attenuation_time(midifile.tracks, seconds=ATTENUATION_SECONDS_AFTER_MUSIC_END)
        self.score.midifile_length = int(midifile.length * 1000)

        if self.run_settings.options.notation_to_midi.save_midifile:
            if self.run_settings.options.notation_to_midi.update_midiplayer_content:
                outfilepath = self.run_settings.notation.midi_out_filepath_midiplayer
            else:
                outfilepath = self.run_settings.notation.midi_out_filepath
            midifile.save(outfilepath)
            self.logger.info(f"File saved as {outfilepath}")

            if self.run_settings.options.notation_to_midi.update_midiplayer_content:
                self.update_midiplayer_content()

        self.logger.info("=====================================")
