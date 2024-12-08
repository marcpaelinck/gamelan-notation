""" Creates a midi file based on a notation file.
    See ./data/README.md for more information about notation files and ./data/notation/test for an example of a notation file.

    Main method: convert_notation_to_midi()
"""

import json
import re

from mido import MidiFile

from src.common.classes import Beat, Gongan, ParserModel, Score
from src.common.constants import DEFAULT, InstrumentPosition, SpecialTags, Stroke
from src.common.lookups import LOOKUP
from src.common.metadata_classes import (
    GonganMeta,
    GonganType,
    GoToMeta,
    KempliMeta,
    LabelMeta,
    MetaData,
    MetaDataSwitch,
    OctavateMeta,
    PartMeta,
    RepeatMeta,
    SilenceMeta,
    SuppressMeta,
    TempoMeta,
    ValidationMeta,
)
from src.common.playercontent_classes import Part, Song
from src.common.utils import (
    create_rest_stave,
    get_whole_rest_note,
    has_kempli_beat,
    most_occurring_beat_duration,
)
from src.notation2midi.midi_track import MidiTrackX
from src.notation2midi.score_validation import (
    add_missing_staves,
    complement_shorthand_pokok_staves,
    validate_score,
)
from src.settings.settings import (
    ATTENUATION_SECONDS_AFTER_MUSIC_END,
    get_midiplayer_content,
    save_midiplayer_content,
)


class Score2MidiConverter(ParserModel):

    score: Score = None

    def __init__(self, score: Score):
        super().__init__(score.settings)
        self.score = score

    def notation_to_track(self, position: InstrumentPosition) -> MidiTrackX:
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
            beat = beat.goto.get(beat._pass_, beat.next)

        return track

    def move_beat_to_start(self) -> None:
        # If the last gongan is regular (has a kempli beat), create an additional gongan with an empty beat
        last_gongan = self.score.gongans[-1]
        if has_kempli_beat(last_gongan):
            new_gongan = Gongan(id=last_gongan.id + 1, beats=[], beat_duration=0)
            self.score.gongans.append(new_gongan)
            last_beat = last_gongan.beats[-1]
            new_beat = Beat(
                id=1,
                sys_id=last_gongan.id + 1,
                bpm_start={-1, last_beat.bpm_end[-1]},
                bpm_end={-1, last_beat.bpm_end[-1]},
                duration=0,
                prev=last_beat,
            )
            last_beat.next = new_beat
            for instrument, notes in last_beat.staves.items():
                new_beat.staves[instrument] = []
            new_gongan.beats.append(new_beat)

        # Iterate through the beats starting from the end.
        # Move the end note of each instrument in the previous beat to the start of the current beat.
        beat = self.score.gongans[-1].beats[-1]
        while beat.prev:
            for instrument, notes in beat.prev.staves.items():
                if notes:
                    # move notes with a total of 1 duration unit
                    notes_to_move = []
                    while notes and sum((note.total_duration for note in notes_to_move), 0) < 1:
                        notes_to_move.insert(0, notes.pop())
                    if not instrument in beat.staves:
                        beat.staves[instrument] = []
                    beat.staves[instrument][0:0] = notes_to_move  # insert at beginning
            # update beat and gongan duration values
            # beat.duration = most_occurring_stave_duration(beat.staves)
            # beat.duration = max(sum(note.total_duration for note in notes) for notes in list(beat.staves.values()))
            # gongan = self.score.gongans[beat.sys_seq]
            # gongan.beat_duration = most_occurring_beat_duration(gongan.beats)
            beat = beat.prev

        # Add a rest at the beginning of the first beat
        for instrument, notes in self.score.gongans[0].beats[0].staves.items():
            notes.insert(0, get_whole_rest_note(Stroke.SILENCE))

    def apply_metadata(self, metadata: list[MetaData], gongan: Gongan) -> None:
        """Processes the metadata of a gongan into the object model.

        Args:
            metadata (list[MetaData]): The metadata to process.
            gongan (Gongan): The gongan to which the metadata applies.
        """

        def process_goto(gongan: Gongan, goto: MetaData) -> None:
            for rep in goto.data.passes or [p + 1 for p in range(10)]:
                # Assuming 10 is larger than the max. number of passes.
                gongan.beats[goto.data.beat_seq].goto[rep] = self.score.flowinfo.labels[goto.data.label]

        haslabel = False  # Will be set to true if the gongan has a metadata Label tag.
        for meta in sorted(metadata, key=lambda x: x.data._processingorder_):
            match meta.data:
                case TempoMeta():
                    if meta.data.beat_count == 0:
                        # immediate tempo change.
                        gongan.beats[meta.data.first_beat_seq].tempo_changes.update(
                            {
                                pass_: Beat.TempoChange(new_tempo=meta.data.bpm, incremental=False)
                                for pass_ in meta.data.passes
                            }
                        )
                    else:
                        # Stepwise tempo change over meta.data.beats beats. The first tempo change is after first beat.
                        # This emulates a gradual tempo change.
                        beat = gongan.beats[meta.data.first_beat_seq]
                        steps = meta.data.beat_count
                        for _ in range(meta.data.beat_count):
                            beat = beat.next
                            if not beat:  # End of score. This should not happen unless notation error.
                                break
                            beat.tempo_changes.update(
                                {
                                    pass_: Beat.TempoChange(new_tempo=meta.data.bpm, steps=steps, incremental=True)
                                    for pass_ in meta.data.passes
                                }
                            )
                            steps -= 1

                case LabelMeta():
                    # Add the label to flowinfo
                    haslabel = True
                    self.score.flowinfo.labels[meta.data.name] = gongan.beats[meta.data.beat_seq]
                    # Process any GoTo pointing to this label
                    goto: MetaData
                    for sys, goto in self.score.flowinfo.gotos[meta.data.name]:
                        process_goto(sys, goto)
                case GoToMeta():
                    # Add goto info to the beat
                    if self.score.flowinfo.labels.get(meta.data.label, None):
                        process_goto(gongan, meta)
                    else:
                        # Label not yet encountered: store GoTo obect in flowinfo
                        self.score.flowinfo.gotos[meta.data.label].append((gongan, meta))
                case RepeatMeta():
                    # Special case of goto: from last back to first beat of the gongan.
                    for counter in range(meta.data.count):
                        gongan.beats[-1].goto[counter + 1] = gongan.beats[0]
                case KempliMeta():
                    # Suppress kempli.
                    # TODO status=ON will never be used because it is the default. So attribute status can be discarded.
                    # Unless a future version enables to switch kempli off until a Kempli ON tag is encountered.
                    if meta.data.status is MetaDataSwitch.OFF:
                        for beat in gongan.beats:
                            # Default is all beats
                            if beat.id in meta.data.beats or not meta.data.beats:
                                beat.has_kempli_beat = False
                case GonganMeta():
                    # TODO: how to safely synchronize all instruments starting from next regular gongan?
                    gongan.gongantype = meta.data.type
                    if gongan.gongantype in [GonganType.GINEMAN, GonganType.KEBYAR]:
                        for beat in gongan.beats:
                            beat.has_kempli_beat = False
                case SuppressMeta():
                    # Add a separate silence stave to the gongan beats for each instrument position and pass mentioned.
                    for beat in gongan.beats:
                        # Default is all beats
                        if beat.id in meta.data.beats or not meta.data.beats:
                            for position in meta.data.positions:
                                beat.exceptions.update(
                                    {
                                        (position, pass_): create_rest_stave(position, Stroke.EXTENSION, beat.duration)
                                        for pass_ in meta.data.passes
                                    }
                                )
                case SilenceMeta():
                    pass
                case ValidationMeta():
                    for beat in [b for b in gongan.beats if b.id in meta.data.beats] or gongan.beats:
                        beat.validation_ignore.extend(meta.data.ignore)
                case OctavateMeta():
                    for beat in gongan.beats:
                        if meta.data.instrument in beat.staves:
                            for idx in range(len(stave := beat.staves[meta.data.instrument])):
                                note = stave[idx]
                                if note.octave != None:
                                    # stave[idx] = note.model_copy(update={"octave": note.octave + meta.data.octaves})
                                    # TODO temporary solution to use Font5Parser
                                    stave[idx] = LOOKUP.get_note(
                                        note.position,
                                        note.pitch,
                                        note.octave + meta.data.octaves,
                                        note.stroke,
                                        note.duration,
                                        note.rest_after,
                                    )
                case PartMeta():
                    pass
                case _:
                    raise ValueError(f"Metadata value {meta.data.metatype} is not supported.")

        if haslabel:
            # Gongan has one or more Label metadata items: explicitly set the current tempo for each beat by copying it
            # from its predecessor. This will ensure that a goto to any of these beats will pick up the correct tempo.
            for beat in gongan.beats:
                if not beat.tempo_changes and beat.prev:
                    beat.tempo_changes.update(beat.prev.tempo_changes)
            return

    def passes_str_to_list(self, rangestr: str) -> list[int]:
        """Converts a pass indicator following a position tag to a list of passes.
            A colon (:) separates the position tag and the pass indicator.
            The indicator has one of the following formats:
            <pass>[,<pass>...]
            <firstpass>-<lastpass>
            where <pass>, <firstpass> and <lastpass> are single digits.
            e.g.:
            gangsa p:2,3

        Args:
            rangestr (str): the pass range indicator, in the prescribed format.

        Raises:
            ValueError: string does not have the expected format.

        Returns:
            list[int]: a list of passes (passes are numbered from 1)
        """
        if not re.match(r"^(\d-\d|(\d,)*\d)$", rangestr):
            raise ValueError(f"Invalid value for passes: {rangestr}")
        if re.match(r"^\d-\d$", rangestr):
            return list(range(int(rangestr[0]), int(rangestr[2]) + 1))
        else:
            return list(json.loads(f"[{rangestr}]"))

    def create_score_object_model(self):
        """Creates an object model of the notation. The method aggregates each note and the corresponding diacritics
        into a single note object, which will simplify the generation of the MIDI file content.

        Args:
            datapath (str): path to the data folder
            infilename (str): name of the csv input file
            title (str): Title for the notation
        """
        beats: list[Beat] = []
        for self.curr_gongan_id, sys_info in self.score.notation_dict.items():
            if self.curr_gongan_id < 0:
                # Skip the gongan holding the global (score-wide) metadata items
                continue
            for self.curr_beat_id, beat_info in sys_info.items():
                if isinstance(self.curr_beat_id, SpecialTags):
                    continue
                # create the staves (regular and exceptions)
                # TODO merge Beat.staves and Beat.exceptions and use pass=-1 for default stave. Similar to Beat.tempo_changes.
                staves = {
                    position: staves[DEFAULT]
                    for position, staves in beat_info.items()
                    if position in InstrumentPosition
                }
                exceptions = {
                    (position, pass_): stave
                    for position, staves in beat_info.items()
                    if position in InstrumentPosition
                    for pass_, stave in staves.items()
                    if pass_ > 0
                }

                # Create the beat and add it to the list of beats
                new_beat = Beat(
                    id=self.curr_beat_id,
                    sys_id=self.curr_gongan_id,
                    staves=staves,
                    exceptions=exceptions,
                    bpm_start={
                        DEFAULT: (bpm := self.score.gongans[-1].beats[-1].bpm_end[-1] if self.score.gongans else 0)
                    },
                    bpm_end={DEFAULT: bpm},
                    duration=max(sum(note.total_duration for note in notes) for notes in list(staves.values())),
                )
                prev_beat = beats[-1] if beats else self.score.gongans[-1].beats[-1] if self.score.gongans else None
                # Update the `next` pointer of the previous beat.
                if prev_beat:
                    prev_beat.next = new_beat
                    new_beat.prev = prev_beat
                beats.append(new_beat)

            # Create a new gongan
            if beats:
                gongan = Gongan(
                    id=int(self.curr_gongan_id),
                    beats=beats,
                    beat_duration=most_occurring_beat_duration(beats),
                    metadata=sys_info.get(SpecialTags.METADATA, [])
                    + self.score.notation_dict[DEFAULT][SpecialTags.METADATA],
                    comments=sys_info.get(SpecialTags.COMMENT, []),
                )
                self.score.gongans.append(gongan)
                beats = []

        # Add extension notes to pokok notation having only one note per beat
        complement_shorthand_pokok_staves(self.score)
        # Add blank staves for all other omitted instruments
        add_missing_staves(score=self.score, add_kempli=False)
        if self.run_settings.notation.beat_at_end:
            # This simplifies the addition of missing staves and correct processing of metadata
            self.move_beat_to_start()
        for gongan in self.score.gongans:
            gongan.beat_duration = most_occurring_beat_duration(gongan.beats)
            self.apply_metadata(gongan.metadata, gongan)
        # Add kempli beats
        add_missing_staves(score=self.score, add_kempli=True)

    def add_attenuation_time(self, tracks: list[MidiTrackX], seconds: int) -> None:
        """Extends the duration of the final note in each channel to avoid an abrupt ending of the audio.

        Args:
            tracks (list[MidiTrackX]): Tracks for which to extend the last note.
            seconds (int): Duration of the extension.
        """
        max_ticks = max(track.total_tick_time() for track in tracks)
        for track in tracks:
            if track.total_tick_time() == max_ticks:
                track.extend_last_note(seconds)

    def create_midifile(self) -> int:
        """Generates the MIDI content and saves it to file.

        Return:
            int: Total duration in milliseconds

        """
        midifile = MidiFile(ticks_per_beat=self.run_settings.midi.PPQ, type=1)

        for position in sorted(self.score.instrument_positions, key=lambda x: x.sequence):
            track = self.notation_to_track(position)
            midifile.tracks.append(track)
        if not self.run_settings.notation.part.loop:
            self.add_attenuation_time(midifile.tracks, seconds=ATTENUATION_SECONDS_AFTER_MUSIC_END)
        if self.run_settings.options.notation_to_midi.save_midifile:
            if self.run_settings.options.notation_to_midi.update_midiplayer_content:
                outfilepath = self.run_settings.notation.midi_out_filepath_midiplayer
            else:
                outfilepath = self.run_settings.notation.midi_out_filepath
            midifile.save(outfilepath)
            self.logger.info(f"File saved as {outfilepath}")
        return int(midifile.length * 1000)

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
            content.songs.append(song := Song(title=self.run_settings.notation.title))
            self.logger.info(f"New song {song.title} created for MIDI player content")
        part = next((part for part in song.parts if part.name == self.score.midiplayer_data.name))
        if not part:
            song.parts.append(
                part := Part(
                    self.score.midiplayer_data.name, self.score.midiplayer_data.file, self.score.midiplayer_data.loop
                )
            )
            self.logger.info(f"New part {part.name} created for MIDI player content")
        else:
            self.logger.info(f"Existing part {part.name} updated for MIDI player content")
            part.file = self.score.midiplayer_data.file
            part.loop = self.score.midiplayer_data.loop
        part.markers = self.markers_millis_to_frac(self.score.midiplayer_data.markers, self.score.total_duration)
        self.logger.info(f"Added time markers to part {part.name}")
        save_midiplayer_content(content)

    def convert_notation_to_midi(self):
        """This method does all the work.
        All settings are read from the (YAML) settings files.
        """
        self.logger.info("======== NOTATION TO MIDI CONVERSION ========")
        self.logger.info(f"input file: {self.run_settings.notation.part.file}")
        self.create_score_object_model()
        if self.has_errors:
            self.logger.info("Program halted.")
            exit()

        validate_score(score=self.score, settings=self.run_settings)

        self.score.total_duration = self.create_midifile()
        if self.run_settings.options.notation_to_midi.update_midiplayer_content:
            self.update_midiplayer_content()
        self.logger.info("=====================================")


if __name__ == "__main__":
    ...
