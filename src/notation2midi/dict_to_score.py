""" Creates a midi file based on a notation file.
    See ./data/README.md for more information about notation files and ./data/notation/test for an example of a notation file.

    Main method: convert_notation_to_midi()
"""

from statistics import mode

from src.common.classes import Beat, Gongan, Measure, Notation, Note, Score
from src.common.constants import (
    DEFAULT,
    Duration,
    NotationDict,
    ParserTag,
    PassSequence,
    Pitch,
    Position,
    RuleType,
    RuleValue,
    Stroke,
    Velocity,
)
from src.common.metadata_classes import (
    AutoKempyungMeta,
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
    SequenceMeta,
    SuppressMeta,
    TempoMeta,
    ValidationMeta,
    ValidationProperty,
    WaitMeta,
)
from src.notation2midi.classes import ParserModel


class DictToScoreConverter(ParserModel):

    notation: Notation = None
    score: Score = None

    POSITIONS_EXPAND_MEASURES = [
        Position.UGAL,
        Position.CALUNG,
        Position.JEGOGAN,
        Position.GONGS,
        Position.KEMPLI,
    ]

    DEFAULT_VELOCITY: Velocity

    def __init__(self, notation: Notation):
        super().__init__(self.ParserType.SCOREGENERATOR, notation.settings)
        self.notation = notation
        self.DEFAULT_VELOCITY = self.run_settings.midi.dynamics[self.run_settings.midi.default_dynamics]

        self.score = Score(
            title=self.run_settings.notation.title,
            settings=notation.settings,
            instrument_positions=self._get_all_positions(notation.notation_dict),
        )

    def _get_all_positions(self, notation_dict: NotationDict) -> set[Position]:
        all_instruments = [
            p
            for gongan_id, gongan in notation_dict.items()
            if gongan_id > 0
            for beat_id, measures in gongan[ParserTag.BEATS].items()
            if isinstance(beat_id, int) and beat_id > 0
            for p in measures.keys()
        ]
        return set(all_instruments)

    def _has_kempli_beat(self, gongan: Gongan):
        return (
            not (kempli := gongan.get_metadata(KempliMeta)) or kempli.status != MetaDataSwitch.OFF
        ) and gongan.gongantype not in [GonganType.KEBYAR, GonganType.GINEMAN]

    def _move_beat_to_start(self) -> None:
        # If the last gongan is regular (has a kempli beat), create an additional gongan with an empty beat
        last_gongan = self.score.gongans[-1]
        if self._has_kempli_beat(last_gongan):
            new_gongan = Gongan(id=last_gongan.id + 1, beats=[], beat_duration=0)
            self.score.gongans.append(new_gongan)
            last_beat = last_gongan.beats[-1]
            new_beat = Beat(
                id=1,
                gongan_id=int(last_gongan.id) + 1,
                bpm_start={DEFAULT: last_beat.bpm_end[-1]},
                bpm_end={DEFAULT: last_beat.bpm_end[-1]},
                # velocity_start and velocity_end are dict[pass, dict[Position, Velocity]]
                velocities_start={DEFAULT: last_beat.velocities_end[DEFAULT].copy()},
                velocities_end={DEFAULT: last_beat.velocities_end[DEFAULT].copy()},
                duration=0,
                prev=last_beat,
            )
            last_beat.next = new_beat
            for position in last_beat.measures.keys():
                new_beat.measures[position] = Measure.new(position=position, notes=[])
                new_gongan.beats.append(new_beat)

        # Iterate through the beats starting from the end.
        # Move the end note of each instrument in the previous beat to the start of the current beat.
        # TODO WARNING: Only the default passes are shifted. Shifting other passes correctly would make this
        # method much more complicated and error prone due to possible unexpected effects of GOTO and LABEL
        # metadata. Therefore notation with kempli beat at the end should be avoided.
        beat = self.score.gongans[-1].beats[-1]
        while beat.prev:
            for position, measure in beat.prev.measures.items():
                if notes := measure.passes[DEFAULT].notes:  # only consider default pass.
                    # move notes with a total of 1 duration unit
                    notes_to_move = []
                    while notes and sum((note.total_duration for note in notes_to_move), 0) < 1:
                        notes_to_move.insert(0, notes.pop())
                    if not position in beat.measures:
                        beat.measures[position] = Measure.new(position=position, notes=[])
                    beat.get_pass(position, DEFAULT).notes[0:0] = notes_to_move  # insert at beginning
            # update beat and gongan duration values
            beat.duration = mode(
                sum(note.total_duration for note in measure.passes[DEFAULT].notes)
                for measure in list(beat.measures.values())
            )
            gongan = self.score.gongans[beat.gongan_seq]
            gongan.beat_duration = mode(beat.duration for beat in gongan.beats)
            beat = beat.prev

        # Add a rest at the beginning of the first beat
        for position, measure in self.score.gongans[0].beats[0].measures.items():
            measure.passes[DEFAULT].notes.insert(0, Note.get_whole_rest_note(position, Stroke.SILENCE))

    def _create_rest_notes(self, position: Position, resttype: Stroke, duration: float) -> list[Note]:
        """Creates a measure with rests of the given type for the given duration.
        If the duration is non-integer, the stameasureve will also contain half and/or quarter rests.

        Args:
            resttype (Stroke): the type of rest (SILENCE or EXTENSION)
            duration (float): the duration, which can be non-integer.

        Returns:
            list[Note]: _description_
        """
        # TODO exception handling
        notes = []
        whole_rest: Note = Note.get_whole_rest_note(position, resttype)
        for i in range(int(duration)):
            notes.append(whole_rest.model_copy(update={"autogenerated": True}))

        # if duration is not integer, add the fractional part as an extra rest.
        if frac_duration := duration - int(duration):
            attribute = "duration" if whole_rest.duration > 0 else "rest_after"
            notes.append(whole_rest.model_copy(update={attribute: frac_duration, "autogenerated": True}))

        return notes

    def _create_rest_measure(
        self, position: Position, resttype: Stroke, duration: float, pass_seq: PassSequence = DEFAULT
    ) -> Measure:
        notes = self._create_rest_notes(position=position, resttype=resttype, duration=duration)
        return Measure.new(position=position, notes=notes, pass_seq=pass_seq)

    def _create_rest_measures(
        self,
        prev_beat: Beat,
        positions: list[Position],
        duration: Duration,
        force_silence: list[Position] = [],
        pass_seq: PassSequence = DEFAULT,
    ):
        silence = Stroke.SILENCE
        extension = Stroke.EXTENSION
        prevstrokes = {
            # We select the default pass because pass_seq might not be the corresponding sequence in prev_beat
            # as a consequence of the flow of the score that will be created in a later stage.
            pos: (prev_beat.get_notes(pos, DEFAULT)[-1].stroke if prev_beat else silence)
            for pos in positions
        }
        # Remark: the resttype is EXTENSION if the previous stroke is MUTED or ABBREVIATED.
        # This will avoid undesired muting when a GOTO points to this measure.
        resttypes = {
            pos: silence if prevstroke is silence or pos in force_silence else extension
            for pos, prevstroke in prevstrokes.items()
        }
        return {
            position: self._create_rest_measure(
                position=position, resttype=resttypes[position], duration=duration, pass_seq=pass_seq
            )
            for position in positions
        }

    def _reverse_kempyung(self, beat: Beat):
        # Only applies to PEMADE_SANGSIH and KANTILAN_SANGSIH.
        # Polos part is expected to be available.
        for measure in beat.measures.values():
            for pass_ in measure.passes.values():
                if pass_.ruletype == RuleType.UNISONO:
                    pass_.notes = [
                        note.get_kempyung(inverse=True) if note.inference_rule == RuleValue.EXACT_KEMPYUNG else note
                        for note in pass_.notes
                    ]

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
            self.curr_line_nr = meta.data.line
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
                case AutoKempyungMeta():
                    if meta.data.status == MetaDataSwitch.ON:
                        # Nothing to do, kempyung is default
                        continue
                    for beat in gongan.beats:
                        self._reverse_kempyung(beat)
                case LabelMeta():
                    # Add the label to flowinfo
                    haslabel = True
                    self.score.flowinfo.labels[meta.data.name] = gongan.beats[meta.data.beat_seq]
                    # Process any GoTo pointing to this label
                    goto: MetaData
                    for gongan_, goto in self.score.flowinfo.gotos[meta.data.name]:
                        process_goto(gongan_, goto)
                case OctavateMeta():
                    for beat in gongan.beats:
                        if meta.data.instrument in beat.measures.keys():
                            for pass_ in self.pass_iterator(beat.measures[meta.data.instrument]):
                                for idx in range(len(notes := pass_.notes)):
                                    note: Note = notes[idx]
                                    if note.octave != None:
                                        note = Note.get_note(
                                            note.position,
                                            note.pitch,
                                            note.octave + meta.data.octaves,
                                            note.stroke,
                                            note.duration,
                                            note.rest_after,
                                        )
                                        if note:
                                            notes[idx] = note
                                        else:
                                            self.logerror(
                                                f"could not octavate note {notes[idx].pitch}{notes[idx].octave} with {meta.data.octaves} octave for {meta.data.instrument}."
                                            )
                case PartMeta():
                    pass
                case RepeatMeta():
                    # Special case of goto: from last back to first beat of the gongan.
                    # for counter in range(meta.data.count):
                    #     gongan.beats[-1].goto[counter + 1] = gongan.beats[0]
                    gongan.beats[-1].repeat = Beat.Repeat(goto=gongan.beats[0], iterations=meta.data.count)
                case SequenceMeta():
                    self.score.flowinfo.sequences.append((gongan, meta.data))
                case SuppressMeta():
                    # Silences the given positions for the given beats and passes.
                    # This is done by adding pass(es) with SILENCE Notes.
                    for beat in gongan.beats:
                        # If no beats are given, default is all beats
                        if beat.id in meta.data.beats or not meta.data.beats:
                            for position in meta.data.positions:
                                if not position in beat.measures.keys():
                                    self.logwarning(
                                        f"Position {position} of {SuppressMeta.metatype} instruction not in gongan."
                                    )
                                    continue
                                line = beat.measures[position].passes[DEFAULT].line
                                for pass_seq in meta.data.passes:
                                    notes = self._create_rest_notes(position, Stroke.EXTENSION, beat.duration)
                                    beat.measures[position].passes[pass_seq] = Measure.Pass(
                                        seq=pass_seq, line=line, notes=notes
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
                        # immediate change.
                        beat = gongan.beats[meta.data.first_beat_seq]
                        beat.changes[changetype].update(
                            {
                                pass_seq: Beat.Change(
                                    new_value=meta.data.value,
                                    positions=meta.data.positions if changetype == Beat.Change.Type.DYNAMICS else [],
                                    incremental=False,
                                )
                                for pass_seq in meta.data.passes
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
                                    pass_seq: Beat.Change(
                                        new_value=meta.data.value,
                                        steps=steps,
                                        positions=(
                                            meta.data.positions if changetype == Beat.Change.Type.DYNAMICS else []
                                        ),
                                        incremental=True,
                                    )
                                    for pass_seq in meta.data.passes
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
                        velocities_start=lastbeat.velocities_start.copy(),
                        velocities_end=lastbeat.velocities_end.copy(),
                        duration=duration,
                        prev=lastbeat,
                        next=lastbeat.next,
                        has_kempli_beat=False,
                        validation_ignore=[ValidationProperty.BEAT_DURATION],
                    )
                    if lastbeat.next:
                        lastbeat.next.prev = newbeat
                        lastbeat.next = newbeat
                    newbeat.measures = self._create_rest_measures(
                        prev_beat=lastbeat, positions=list(lastbeat.measures.keys()), duration=duration
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

    def _process_sequences(self):
        """Translates the labels of the sequences into goto directives in the respective beats."""
        for initial_gongan, sequence in self.score.flowinfo.sequences:
            gongan = initial_gongan
            for label in sequence.value:
                from_beat = gongan.beats[-1]  # Sequence always links last beat to first beat of next gongan in the list
                to_beat = self.score.flowinfo.labels[label]
                pass_nr = max([p for p in from_beat.goto.keys()] or [0]) + 1  # Select next available pass
                from_beat.goto[pass_nr] = to_beat
                gongan = self.score.gongans[to_beat.gongan_seq]

    def _create_missing_measures(
        self, beat: Beat, prevbeat: Beat, all_instruments: list[Position], force_silence=[]
    ) -> dict[Position, Measure]:
        """Returns measures for missing positions, containing rests (silence) for the duration of the given beat.
                This ensures that positions that do not occur in all the gongans will remain in sync.
        2
                Args:
                    beat (Beat): The beat that should be complemented.
                    all_positions (set[Position]): List of all the positions that occur in the notation.

                Returns:
                    dict[Position, Measure]: A dict with the generated measures.
        """

        # a kempli beat is a muted stroke
        KEMPLI_BEAT = Note.get_note(
            Position.KEMPLI, pitch=Pitch.STRIKE, octave=None, stroke=Stroke.MUTED, duration=1, rest_after=0
        )
        # add rests to existing but empty measures
        for position, measure in beat.measures.items():
            for pass_seq, pass_ in measure.passes.items():
                if not pass_.notes:
                    resttype = (
                        Stroke.SILENCE
                        if position in force_silence
                        or prevbeat.get_notes(position, DEFAULT)[-1].stroke is Stroke.SILENCE
                        else Stroke.EXTENSION
                    )
                    pass_.notes = self._create_rest_notes(position=position, resttype=resttype, duration=beat.duration)
        # add measures for missing positions
        if missing_positions := (all_instruments - set(pos for pos in beat.measures.keys() if beat.measures[pos])):
            measures = self._create_rest_measures(
                prev_beat=prevbeat, positions=missing_positions, duration=beat.duration, force_silence=force_silence
            )

            # Add a kempli beat, except if a metadata label indicates otherwise or if the kempli part was already given in the original score
            if Position.KEMPLI in measures.keys():  # and has_kempli_beat(gongan):
                if beat.has_kempli_beat:
                    rests = self._create_rest_notes(Position.KEMPLI, Stroke.EXTENSION, beat.duration - 1)
                    measures[Position.KEMPLI] = Measure.new(position=Position.KEMPLI, notes=[KEMPLI_BEAT] + rests)
                else:
                    measures[Position.KEMPLI] = self._create_rest_measure(
                        Position.KEMPLI, Stroke.EXTENSION, beat.duration
                    )

            return measures
        else:
            return dict()

    def _add_missing_measures(self, add_kempli: bool = True):
        prev_beat = None
        for gongan in self.gongan_iterator(self.score):
            all_instruments = self.score.instrument_positions | (
                {Position.KEMPLI} if add_kempli else self.score.instrument_positions
            )
            gongan_missing_instr = [
                pos for pos in all_instruments if all(pos not in beat.measures for beat in gongan.beats)
            ]
            for beat in self.beat_iterator(gongan):
                # Not all positions occur in each gongan.
                # Therefore we need to add blank measure (all rests) for missing positions.
                # If an instrument is missing in the entire gongan, the last beat should consist
                # of silences (.) rather than note extensions (-). This avoids unexpected results when the next beat
                # is repeated and the kempli beat is at the end of the beat.
                force_silence = gongan_missing_instr if beat == gongan.beats[-1] else []
                missing_measures = self._create_missing_measures(
                    beat, prev_beat, all_instruments, force_silence=force_silence
                )
                beat.measures.update(missing_measures)
                # Update all positions of the score
                self.score.instrument_positions.update({pos for pos in missing_measures})
                prev_beat = beat

    def _extend_measure(self, position: Position, notes: list[Note], duration: float):
        """Extend a measure with EXTENSION notes so that its length matches the required duration.

        Args:
            position (Position): instrument position
            notes (list[Note]): the measure content that should be extended
            duration (float): target duration
        """
        filler = Note.get_whole_rest_note(position, Stroke.EXTENSION)
        measure_duration = sum(note.total_duration for note in notes)
        # Add rests of duration 1 to match the integer part of the beat's duration
        if int(duration - measure_duration) >= 1:
            fill_content = [
                filler.model_copy(update={"autogenerated": True}) for count in range(int(duration - len(notes)))
            ]
            if self.score.settings.notation.beat_at_end:
                fill_content.extend(notes)
                notes.clear()
                notes.extend(fill_content)
            else:
                notes.extend(fill_content)
            measure_duration = sum(note.total_duration for note in notes)
        # Add an extra rest for any fractional part of the beat's duration
        if measure_duration < duration:
            attr = "duration" if filler.stroke == Stroke.EXTENSION else "rest_after"
            notes.append(filler.model_copy(update={attr: duration - measure_duration, "autogenerated": True}))

    def _complement_shorthand_pokok_measures(self):
        """Adds EXTENSION notes to pokok measures that only contain one note (shorthand notation)"""

        for gongan in self.gongan_iterator(self.score):
            for beat in self.beat_iterator(gongan):
                for position, measure in beat.measures.items():
                    for pass_ in self.pass_iterator(measure):
                        if (
                            position in self.POSITIONS_EXPAND_MEASURES
                            and sum(note.total_duration for note in pass_.notes) != beat.duration
                        ):
                            self._extend_measure(position=position, notes=pass_.notes, duration=beat.duration)

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
            for self.curr_beat_id, measures in gongan_info[ParserTag.BEATS].items():
                # Create the beat and add it to the list of beats
                new_beat = Beat(
                    id=int(self.curr_beat_id),
                    gongan_id=int(self.curr_gongan_id),
                    measures=measures,
                    bpm_start={
                        DEFAULT: (bpm := self.score.gongans[-1].beats[-1].bpm_end[-1] if self.score.gongans else 0)
                    },
                    bpm_end={DEFAULT: bpm},
                    velocities_start={
                        DEFAULT: (
                            # velocity_start and velocity_end are dict[pass, dict[Position, Velocity]]
                            vel := (
                                self.score.gongans[-1].beats[-1].velocities_end[-1].copy()
                                if self.score.gongans
                                else {pos: self.DEFAULT_VELOCITY for pos in Position}
                            )
                        )
                    },
                    velocities_end={DEFAULT: vel.copy()},
                    # TODO Shouldn't we use mode instead of max? Makes a difference for error logging.
                    # Answer: not here, because at this stage, pokok positions with length 1 haven't been extended yet.
                    duration=max(
                        sum(note.total_duration for note in measure.passes[DEFAULT].notes)
                        for measure in measures.values()
                    ),
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
                    beat_duration=mode(beat.duration for beat in beats),  # most occuring duration
                    metadata=gongan_info.get(ParserTag.METADATA, [])
                    + self.notation.notation_dict[DEFAULT][ParserTag.METADATA],
                    comments=gongan_info.get(ParserTag.COMMENTS, []),
                )
                self.score.gongans.append(gongan)
                beats = []

        # Add extension notes to pokok notation having only one note per beat
        try:
            self._complement_shorthand_pokok_measures()
        except Exception as error:
            self.logerror(str(error))

        # Add blank measures for all other omitted instruments
        self._add_missing_measures(add_kempli=False)
        if self.run_settings.notation.beat_at_end:
            # This enables correct processing of metadata
            self._move_beat_to_start()
        for gongan in self.gongan_iterator(self.score):
            # TODO temporary fix. Create generators to iterate through gongans, beats and positions
            # These should update the curr counters.
            gongan.beat_duration = max(beat.duration for beat in gongan.beats)  # most occuring duration
            self._apply_metadata(gongan.metadata, gongan)
        # Process the sequences metadata
        self._process_sequences()
        # Add kempli beats
        self._add_missing_measures(add_kempli=True)

    def create_score(self):
        """This method does all the work.
        All settings are read from the (YAML) settings files.
        """
        self.logger.info("======== NOTATION TO MIDI CONVERSION ========")
        self.logger.info(f"input file: {self.run_settings.notation.part.file}")
        self._create_score_object_model()
        if self.has_errors:
            self.logerror("Program halted.")
            exit()

        return self.score


if __name__ == "__main__":
    pass
