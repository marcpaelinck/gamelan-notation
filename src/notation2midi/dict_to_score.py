""" Creates a midi file based on a notation file.
    See ./data/README.md for more information about notation files and ./data/notation/test for an example of a notation file.

    Main method: convert_notation_to_midi()
"""

from common.playercontent_classes import Part
from src.common.classes import Beat, Gongan, Notation, Note, ParserModel, Score
from src.common.constants import (
    DEFAULT,
    NotationDict,
    Pitch,
    Position,
    SpecialTags,
    Stroke,
)
from src.common.lookups import LOOKUP
from src.common.metadata_classes import (
    DynamicsMeta,
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
    SuppressMeta,
    TempoMeta,
    ValidationMeta,
    ValidationProperty,
    WaitMeta,
)
from src.common.utils import (
    create_rest_stave,
    create_rest_staves,
    get_whole_rest_note,
    has_kempli_beat,
    most_occurring_beat_duration,
)


class DictToScoreConverter(ParserModel):

    notation: Notation = None
    score: Score = None

    POSITIONS_EXPAND_STAVES = [
        Position.UGAL,
        Position.CALUNG,
        Position.JEGOGAN,
        Position.GONGS,
        Position.KEMPLI,
    ]

    def __init__(self, notation: Notation):
        super().__init__(self.ParserType.SCOREGENERATOR, notation.settings)
        self.notation = notation
        self.score = Score(
            title=self.run_settings.notation.title,
            settings=notation.settings,
            instrument_positions=self._get_all_positions(notation.notation_dict),
            position_range_lookup=LOOKUP.POSITION_P_O_S_TO_NOTE,  # replace with LOOKUP
        )

    def _get_all_positions(self, notation_dict: NotationDict) -> set[Position]:
        all_instruments = [
            p
            for gongan_id, gongan in notation_dict.items()
            if gongan_id > 0
            for stave_id, staves in gongan.items()
            if isinstance(stave_id, int) and stave_id > 0
            for p in staves.keys()
        ]
        return set(all_instruments)

    def _move_beat_to_start(self) -> None:
        # If the last gongan is regular (has a kempli beat), create an additional gongan with an empty beat
        last_gongan = self.score.gongans[-1]
        if has_kempli_beat(last_gongan):
            new_gongan = Gongan(id=last_gongan.id + 1, beats=[], beat_duration=0)
            self.score.gongans.append(new_gongan)
            last_beat = last_gongan.beats[-1]
            new_beat = Beat(
                id=1,
                gongan_id=last_gongan.id + 1,
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
            # gongan = self.score.gongans[beat.gongan_seq]
            # gongan.beat_duration = most_occurring_beat_duration(gongan.beats)
            beat = beat.prev

        # Add a rest at the beginning of the first beat
        for instrument, notes in self.score.gongans[0].beats[0].staves.items():
            notes.insert(0, get_whole_rest_note(Stroke.SILENCE))

    def _apply_metadata(self, metadata: list[MetaData], gongan: Gongan) -> None:
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
                case GonganMeta():
                    # TODO: how to safely synchronize all instruments starting from next regular gongan?
                    gongan.gongantype = meta.data.type
                    if gongan.gongantype in [GonganType.GINEMAN, GonganType.KEBYAR]:
                        for beat in gongan.beats:
                            beat.has_kempli_beat = False
                case GoToMeta():
                    # Add goto info to the beat
                    if self.score.flowinfo.labels.get(meta.data.label, None):
                        process_goto(gongan, meta)
                    else:
                        # Label not yet encountered: store GoTo obect in flowinfo
                        self.score.flowinfo.gotos[meta.data.label].append((gongan, meta))
                case KempliMeta():
                    # Suppress kempli.
                    # TODO status=ON will never be used because it is the default. So attribute status can be discarded.
                    # Unless a future version enables to switch kempli off until a Kempli ON tag is encountered.
                    if meta.data.status is MetaDataSwitch.OFF:
                        for beat in gongan.beats:
                            # Default is all beats
                            if beat.id in meta.data.beats or not meta.data.beats:
                                beat.has_kempli_beat = False
                case LabelMeta():
                    # Add the label to flowinfo
                    haslabel = True
                    self.score.flowinfo.labels[meta.data.name] = gongan.beats[meta.data.beat_seq]
                    # Process any GoTo pointing to this label
                    goto: MetaData
                    for gongan, goto in self.score.flowinfo.gotos[meta.data.name]:
                        process_goto(gongan, goto)
                case OctavateMeta():
                    for beat in gongan.beats:
                        if meta.data.instrument in beat.staves:
                            for idx in range(len(stave := beat.staves[meta.data.instrument])):
                                note = stave[idx]
                                if note.octave != None:
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
                case RepeatMeta():
                    # Special case of goto: from last back to first beat of the gongan.
                    # for counter in range(meta.data.count):
                    #     gongan.beats[-1].goto[counter + 1] = gongan.beats[0]
                    gongan.beats[-1].repeat = Beat.Repeat(goto=gongan.beats[0], iterations=meta.data.count)
                case SuppressMeta():
                    # Silences the given positions for the given beats and passes.
                    # This is done by adding "silence" staves to the `exception` list of the beat.
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
                case TempoMeta() | DynamicsMeta():
                    changetype = (
                        Beat.Change.Type.TEMPO if isinstance(meta.data, TempoMeta) else Beat.Change.Type.DYNAMICS
                    )
                    if (
                        first_too_large := meta.data.first_beat > len(gongan.beats)
                    ) or meta.data.first_beat + meta.data.beat_count - 1 > len(gongan.beats):
                        value = "first_beat" + (" + beat_count" if not first_too_large else "")
                        self.logerror(f"{meta.data.metatype} metadata: {value} is larger than the number of beats")
                        continue
                    if meta.data.beat_count == 0:
                        # immediate tempo change.
                        beat = gongan.beats[meta.data.first_beat_seq]
                        beat.changes[changetype].update(
                            {
                                pass_: Beat.Change(new_value=meta.data.value, incremental=False)
                                for pass_ in meta.data.passes
                            }
                        )
                    else:
                        # Stepwise change over meta.data.beats beats. The first change is after first beat.
                        # This emulates a gradual tempo change.
                        beat = gongan.beats[meta.data.first_beat_seq]
                        steps = meta.data.beat_count
                        for _ in range(meta.data.beat_count):
                            beat = beat.next
                            if not beat:  # End of score. This should not happen unless notation error.
                                break
                            beat.changes[changetype].update(
                                {
                                    pass_: Beat.Change(new_value=meta.data.value, steps=steps, incremental=True)
                                    for pass_ in meta.data.passes
                                }
                            )
                            steps -= 1
                case ValidationMeta():
                    for beat in [b for b in gongan.beats if b.id in meta.data.beats] or gongan.beats:
                        beat.validation_ignore.extend(meta.data.ignore)
                case WaitMeta():
                    # Add a beat with silences at the end of the gongan. The beat's bpm is set to 60 for easy calculation.
                    lastbeat = gongan.beats[-1]
                    duration = round(4 * meta.data.seconds)  # 4 notes per bpm unit and bpm=60 => 4 notes per second.
                    newbeat = Beat(
                        id=lastbeat.id + 1,
                        gongan_id=gongan.id,
                        bpm_start={-1: 60},
                        bpm_end=lastbeat.bpm_end,
                        duration=duration,
                        prev=lastbeat,
                        next=lastbeat.next,
                        has_kempli_beat=False,
                        validation_ignore=[ValidationProperty.BEAT_DURATION],
                    )
                    lastbeat.next.prev = newbeat
                    lastbeat.next = newbeat
                    newbeat.staves = create_rest_staves(
                        prev_beat=lastbeat, positions=lastbeat.staves.keys(), duration=duration
                    )
                    gongan.beats.append(newbeat)
                case _:
                    raise ValueError(f"Metadata value {meta.data.metatype} is not supported.")

        if haslabel:
            # Gongan has one or more Label metadata items: explicitly set the current tempo for each beat by copying it
            # from its predecessor. This will ensure that a goto to any of these beats will pick up the correct tempo.
            for beat in gongan.beats:
                if not beat.changes and beat.prev:
                    beat.changes.update(beat.prev.changes)
            return

    def _create_missing_staves(
        self, beat: Beat, prevbeat: Beat, add_kempli: bool = True, force_silence=[]
    ) -> dict[Position, list[Note]]:
        """Returns staves for missing positions, containing rests (silence) for the duration of the given beat.
        This ensures that positions that do not occur in all the gongans will remain in sync.

        Args:
            beat (Beat): The beat that should be complemented.
            all_positions (set[Position]): List of all the positions that occur in the notation.

        Returns:
            dict[Position, list[Note]]: A dict with the generated staves.
        """

        all_instruments = (
            self.score.instrument_positions | {Position.KEMPLI} if add_kempli else self.score.instrument_positions
        )
        # a kempli beat is a muted stroke
        # Note: these two line are BaliMusic5 font exclusive!
        KEMPLI_BEAT = LOOKUP.get_note(
            Position.KEMPLI, pitch=Pitch.STRIKE, octave=None, stroke=Stroke.MUTED, duration=1, rest_after=0
        )

        if missing_positions := (all_instruments - set(beat.staves.keys())):
            staves = create_rest_staves(
                prev_beat=prevbeat, positions=missing_positions, duration=beat.duration, force_silence=force_silence
            )

            # Add a kempli beat, except if a metadata label indicates otherwise or if the kempli part was already given in the original score
            if Position.KEMPLI in staves.keys():  # and has_kempli_beat(gongan):
                if beat.has_kempli_beat:
                    rests = create_rest_stave(Position.KEMPLI, Stroke.EXTENSION, beat.duration - 1)
                    staves[Position.KEMPLI] = [KEMPLI_BEAT] + rests
                else:
                    all_rests = create_rest_stave(Position.KEMPLI, Stroke.EXTENSION, beat.duration)
                    staves[Position.KEMPLI] = all_rests

            return staves
        else:
            return dict()

    def _add_missing_staves(self, add_kempli: bool = True):
        prev_beat = None
        for gongan in self.gongan_iterator(self.score):
            gongan_missing_instr = [pos for pos in Position if all(pos not in beat.staves for beat in gongan.beats)]
            for beat in self.beat_iterator(gongan):
                # Not all positions occur in each gongan.
                # Therefore we need to add blank staves (all rests) for missing positions.
                # If an instrument is missing in the entire gongan, the last beat should consist
                # of silences (.) rather than note extensions (-). This avoids unexpected results when the next beat
                # is repeated and the kempli beat is at the end of the beat.
                force_silence = gongan_missing_instr if beat == gongan.beats[-1] else []
                missing_staves = self._create_missing_staves(beat, prev_beat, add_kempli, force_silence=force_silence)
                beat.staves.update(missing_staves)
                # Update all positions of the score
                self.score.instrument_positions.update({pos for pos in missing_staves})
                prev_beat = beat

    def _extend_stave(self, position: Position, notes: list[Note], duration: float):
        """Extend a stave with EXTENSION notes so that its length matches the required duration.

        Args:
            position (Position): instrument position of the stave
            notes (list[Note]): the stave content
            duration (float): target duration
        """
        filler = get_whole_rest_note(position, Stroke.EXTENSION)
        stave_duration = sum(note.total_duration for note in notes)
        # Add rests of duration 1 to match the integer part of the beat's duration
        if int(duration - stave_duration) >= 1:
            fill_content = [filler.model_copy() for count in range(int(duration - len(notes)))]
            if self.score.settings.notation.beat_at_end:
                fill_content.extend(notes)
                notes.clear()
                notes.extend(fill_content)
            else:
                notes.extend(fill_content)
            stave_duration = sum(note.total_duration for note in notes)
        # Add an extra rest for any fractional part of the beat's duration
        if stave_duration < duration:
            attr = "duration" if filler.stroke == Stroke.EXTENSION else "rest_after"
            notes.append(filler.model_copy(update={attr: duration - stave_duration}))

    def _complement_shorthand_pokok_staves(self):
        """Adds EXTENSION notes to pokok staves that only contain one note (shorthand notation)

        Args:
            gongan_iterator (Generator): iterates through all gongans
        """

        for gongan in self.gongan_iterator(self.score):
            for beat in self.beat_iterator(gongan):
                for position, notes in beat.staves.items():
                    if (
                        position in self.POSITIONS_EXPAND_STAVES
                        and sum(note.total_duration for note in notes) != beat.duration
                    ):
                        self._extend_stave(position=position, notes=notes, duration=beat.duration)

    def _create_score_object_model(self) -> Score:
        """Creates an object model of the notation. The method aggregates each note and the corresponding diacritics
        into a single note object, which will simplify the generation of the MIDI file content.

        Args:
            datapath (str): path to the data folder
            infilename (str): name of the csv input file
            title (str): Title for the notation

        Returns:
            Score: A Score object model, not yet validated for inconsistencies.
        """
        beats: list[Beat] = []
        for self.curr_gongan_id, gongan_info in self.notation.notation_dict.items():
            if self.curr_gongan_id < 0:
                # Skip the gongan holding the global (score-wide) metadata items
                continue
            for self.curr_beat_id, beat_info in gongan_info.items():
                if isinstance(self.curr_beat_id, SpecialTags):
                    continue
                # create the staves (regular and exceptions)
                # TODO merge Beat.staves and Beat.exceptions and use pass=-1 for default stave. Similar to Beat.tempo_changes.
                staves = {position: staves[DEFAULT] for position, staves in beat_info.items() if position in Position}
                exceptions = {
                    (position, pass_): stave
                    for position, staves in beat_info.items()
                    if position in Position
                    for pass_, stave in staves.items()
                    if pass_ > 0
                }

                # Create the beat and add it to the list of beats
                new_beat = Beat(
                    id=self.curr_beat_id,
                    gongan_id=self.curr_gongan_id,
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
                    metadata=gongan_info.get(SpecialTags.METADATA, [])
                    + self.notation.notation_dict[DEFAULT][SpecialTags.METADATA],
                    comments=gongan_info.get(SpecialTags.COMMENT, []),
                )
                self.score.gongans.append(gongan)
                beats = []

        # Add extension notes to pokok notation having only one note per beat
        gongan_iterator = self.gongan_iterator(self.score)
        try:
            self._complement_shorthand_pokok_staves()
        except Exception as error:
            self.logerror(str(error))

        # Add blank staves for all other omitted instruments
        self._add_missing_staves(add_kempli=False)
        if self.run_settings.notation.beat_at_end:
            # This simplifies the addition of missing staves and correct processing of metadata
            self._move_beat_to_start()
        for gongan in self.gongan_iterator(self.score):
            # TODO temporary fix. Create generators to iterate through gongans, beats and positions
            # These should update the curr counters.
            gongan.beat_duration = most_occurring_beat_duration(gongan.beats)
            self._apply_metadata(gongan.metadata, gongan)
        # Add kempli beats
        self._add_missing_staves(add_kempli=True)

    def convert_notation_to_midi(self):
        """This method does all the work.
        All settings are read from the (YAML) settings files.
        """
        self.logger.info("======== NOTATION TO MIDI CONVERSION ========")
        self.logger.info(f"input file: {self.run_settings.notation.part.file}")
        self._create_score_object_model()
        if self.has_errors:
            self.logger.info("Program halted.")
            exit()

        return self.score


if __name__ == "__main__":
    ...
