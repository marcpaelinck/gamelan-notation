import math
from itertools import product
from typing import Any, override

from src.common.classes import Beat, Gongan, Score
from src.common.constants import (
    DEFAULT,
    BeatId,
    Duration,
    InstrumentGroup,
    InstrumentType,
    Octave,
    Pitch,
    Position,
    Stroke,
)
from src.common.notes import Note, NoteFactory
from src.notation2midi.classes import Agent
from src.notation2midi.metadata_classes import GonganType, ValidationProperty
from src.settings.classes import RunSettings


class ScoreValidationAgent(Agent):

    LOGGING_MESSAGE = "VALIDATING SCORE"
    EXPECTED_INPUT_TYPES = (Agent.InputOutputType.RUNSETTINGS, Agent.InputOutputType.COMPLETESCORE)
    RETURN_TYPE = None
    POSITIONS_AUTOCORRECT_UNEQUAL_MEASURES = [
        Position.UGAL,
        Position.CALUNG,
        Position.JEGOGAN,
        Position.GONGS,
        Position.KEMPLI,
    ]
    POSITIONS_VALIDATE_AND_CORRECT_KEMPYUNG = [
        (Position.PEMADE_POLOS, Position.PEMADE_SANGSIH),
        (Position.KANTILAN_POLOS, Position.KANTILAN_SANGSIH),
    ]

    def __init__(self, run_settings: RunSettings, complete_score: Score):
        super().__init__(run_settings)
        self.score = complete_score

    @override
    @classmethod
    def run_condition_satisfied(cls, run_settings: RunSettings):
        return run_settings.options.notation_to_midi

    def _invalid_beat_lengths(self, gongan: Gongan, autocorrect: bool) -> tuple[list[tuple[BeatId, Duration]]]:
        """Checks the length of beats in "regular" gongans. The length should be a power of 2.

        Args:
            gongan (Gongan): the gongan to check
            autocorrect (bool): if True, an attempt will be made to correct the beat length (currently not effective)

        Returns:
            tuple[list[tuple[BeatId, Duration]]]: list of remaining invalid beats and of corrected beats.
        """
        invalids = []
        corrected = []
        ignored = []

        for beat in gongan.beats:
            if ValidationProperty.BEAT_DURATION in beat.validation_ignore:
                ignored.append(f"BEAT {beat.full_id} skipped due to override")
                continue
            if gongan.gongantype == GonganType.REGULAR and 2 ** int(math.log2(beat.duration)) != beat.duration:
                invalids.append((beat.full_id, beat.duration))
        return invalids, corrected, ignored

    def _unequal_measure_lengths(
        self, gongan: Gongan, beat_at_end: bool, autocorrect: bool
    ) -> tuple[list[tuple[BeatId, Duration]]]:
        """Checks that the measure lengths of the individual instrument in each beat of the given gongan are all equal.

        Args:
            gongan (Gongan): the gongan to check
            autocorrect (bool): if True, an attempt will be made to correct the measure lengths of specific instruments (pokok, gongs and kempli)
                        In most scores, the notation of these instruments is simplified by omitting dashes (extensions) after each long note.
            filler (Note): Note representing the extension of the preceding note with duration 1 (a dash in the notation)

        Returns:
            tuple[list[tuple[BeatId, Duration]]]: list of remaining invalid beats and of corrected beats.
        """
        invalids = []
        corrected = []
        ignored = []

        for beat in self.beat_iterator(gongan):
            if ValidationProperty.MEASURE_LENGTH in beat.validation_ignore:
                ignored.append(f"BEAT {beat.full_id} skipped due to override")
                continue
            # Check if the length of all measures in a beat are equal.
            self.curr_line_nr = list(beat.measures.values())[0].passes[DEFAULT].line
            unequal_lengths = {
                position: measure.passes[DEFAULT].notes
                for position, measure in beat.measures.items()
                if measure.duration != beat.duration
            }
            if unequal_lengths:
                if autocorrect:
                    # Autocorrection is performed using beat.duration as a reference,
                    #  which is the mode (= most occurring duration) of all measure durations.
                    corrected_positions = dict()
                    for position, notes in unequal_lengths.items():
                        filler = NoteFactory.get_whole_rest_note(position, Stroke.EXTENSION)
                        uncorrected_position = {position: sum(note.pattern_duration for note in notes)}
                        # Empty measures will always be corrected.
                        if position in self.POSITIONS_AUTOCORRECT_UNEQUAL_MEASURES or not notes:
                            measure_duration = sum(note.pattern_duration for note in notes)
                            # Add rests of duration 1 to match the integer part of the beat's duration
                            if int(beat.duration - measure_duration) >= 1:
                                fill_content = [filler.model_copy() for count in range(int(beat.duration - len(notes)))]
                                if beat_at_end:
                                    fill_content.extend(notes)
                                    notes.clear()
                                    notes.extend(fill_content)
                                else:
                                    notes.extend(fill_content)
                                measure_duration = sum(note.pattern_duration for note in notes)
                            # Add an extra rest for any fractional part of the beat's duration
                            if measure_duration < beat.duration:
                                attr = "duration" if filler.stroke == Stroke.EXTENSION else "rest_after"
                                notes.append(filler.model_copy(update={attr: beat.duration - measure_duration}))
                            if sum(note.pattern_duration for note in notes) == beat.duration:
                                # store the original (incorrect) value
                                corrected_positions |= uncorrected_position
                    if corrected_positions:
                        corrected.append({"BEAT " + beat.full_id: beat.duration} | corrected_positions)

                unequal_lengths = {
                    position: measure.passes[DEFAULT].notes
                    for position, measure in beat.measures.items()
                    if sum(note.pattern_duration for note in measure.passes[DEFAULT].notes) != beat.duration
                }
                if unequal_lengths:
                    invalids.append(
                        {f"BEAT {beat.full_id} line {self.curr_line_nr}": {beat.duration}}
                        | {pos: sum(note.pattern_duration for note in notes) for pos, notes in unequal_lengths.items()},
                    )
        return invalids, corrected, ignored

    def _out_of_range(self, gongan: Gongan, autocorrect: bool) -> tuple[list[str, list[Note]]]:
        """Checks that the notes of each instrument matches the instrument's range.

        Args:
            gongan (Gongan): the gongan to check
            autocorrect (bool): if True, an attempt will be made to correct notes that are out of range (currently not effective)

        Returns:
            tuple[list[tuple[BeatId, Duration]]]: list of remaining beats containing incorrect notes and of corrected beats.
        """
        invalids = []
        corrected = []
        ignored = []

        for beat in self.beat_iterator(gongan):
            if ValidationProperty.INSTRUMENT_RANGE in beat.validation_ignore:
                ignored.append(f"BEAT {beat.full_id} skipped due to override")
                continue
            for position, measure in beat.measures.items():
                instr_range = NoteFactory.get_all_p_o_s(position)
                badnotes = list()
                for note in measure.passes[DEFAULT].notes:
                    if note.pitch is not Pitch.NONE and (note.pitch, note.octave, note.stroke) not in instr_range:
                        badnotes.append((note.pitch, note.octave, note.stroke))
                if badnotes:
                    invalids.append({f"BEAT {beat.full_id} {position}": badnotes})
        return invalids, corrected, ignored

    def _get_kempyung_dict(self, instrumentrange: dict[tuple[Pitch, Octave, Stroke], tuple[Pitch, Octave]]):
        """returns a dict mapping the kempyung note to each base note in the instrument's range.

        Args:
            instrumentrange (list[tuple[Pitch, Octave, Stroke]]): range of the instrument.

        Returns:
            dict[tuple[Pitch, Octave], tuple[Pitch, Octave]]: the kempyung dict
        """
        # CURRENLTY GONG KEBYAR ONLY
        all_notes = sorted(
            list(product([Pitch.DING, Pitch.DONG, Pitch.DENG, Pitch.DUNG, Pitch.DANG], [0, 1, 2])),
            key=lambda x: x[0].sequence + x[1] * 10,
        )
        base_dict = list(zip(all_notes, all_notes[3:]))
        kempyung_dict = {p: s if s in instrumentrange else p for (p, s) in base_dict if p in instrumentrange}
        return kempyung_dict

    def _incorrect_kempyung(
        self,
        gongan: Gongan,
        autocorrect: bool,
    ) -> list[tuple[BeatId, tuple[Position, Position]]]:
        # TODO: currently only works for gong kebyar, not for semar pagulingan

        def note_pairs(beat: Beat, pair: list[InstrumentType]):
            return list(
                zip(
                    beat.measures[pair[0]].passes[DEFAULT].notes,
                    beat.measures[pair[1]].passes[DEFAULT].notes,
                )
            )

        invalids = []
        corrected = []
        ignored = []
        for beat in self.beat_iterator(gongan):
            if ValidationProperty.KEMPYUNG in beat.validation_ignore:
                ignored.append(f"BEAT {beat.full_id} skipped due to override")
                continue
            for polos, sangsih in self.POSITIONS_VALIDATE_AND_CORRECT_KEMPYUNG:
                instrumentrange = [
                    (pitch, octave)
                    for (pitch, octave, stroke) in NoteFactory.get_all_p_o_s(polos)
                    if stroke == Stroke.OPEN
                ]
                kempyung_dict = self._get_kempyung_dict(instrumentrange)
                # check if both instruments occur in the beat
                if all(instrument in beat.measures.keys() for instrument in (polos, sangsih)):
                    # check each kempyung note
                    notepairs = note_pairs(beat, (polos, sangsih))
                    incorrect_detected = False
                    autocorrected = False
                    # only check kempyung if parts are homophone.
                    if all(
                        polos.stroke == sangsih.stroke  # Unisono and playing the same stroke (muting, open or rest)
                        and polos.duration == sangsih.duration
                        and polos.rest_after == sangsih.rest_after
                        for polos, sangsih in notepairs
                    ):
                        orig_sangsih_str = "".join((n.symbol for n in beat.get_notes(sangsih, DEFAULT)))
                        # Check for incorrect sangsih values.
                        # When autocorrecting, run the code a second time to check for remaining errors.
                        iterations = [1, 2] if autocorrect else [1]
                        for iteration in iterations:
                            notepairs = note_pairs(beat, (polos, sangsih))
                            for seq, (polosnote, sangsihnote) in enumerate(notepairs):
                                # Check kempyung.
                                if (
                                    polosnote.pitch is not Pitch.NONE
                                    and sangsihnote.pitch is not Pitch.NONE
                                    and not (sangsihnote.pitch, sangsihnote.octave)
                                    == kempyung_dict[(polosnote.pitch, polosnote.octave)]
                                ):
                                    if autocorrect and iteration == 2:
                                        correct_pitch, correct_octave = kempyung_dict[
                                            (polosnote.pitch, polosnote.octave)
                                        ]
                                        correct_sangsih = Note(
                                            position=sangsih,
                                            pitch=correct_pitch,
                                            octave=correct_octave,
                                            stroke=sangsihnote.stroke,
                                            note_value=sangsihnote.note_value,
                                            generic_note=sangsihnote.generic_note,
                                        )
                                        # Replace the note pattern
                                        # pylint: disable=no-member
                                        # correct_sangsih.pattern.clear()
                                        # correct_sangsih.pattern.append(correct_sangsih.to_pattern_note())
                                        # pylint: enable=no-member
                                        if not (correct_sangsih):
                                            self.logerror(
                                                f"Trying to create an incorrect combination {sangsih} {correct_pitch} OCT{correct_octave} {sangsihnote.stroke} duration={sangsihnote.duration} rest_after{sangsihnote.rest_after} while correcting kempyung."
                                            )
                                        beat.get_notes(sangsih, DEFAULT)[seq] = correct_sangsih
                                        autocorrected = True
                                    elif iteration == iterations[-1]:
                                        # Last iterations
                                        incorrect_detected = True

                    if incorrect_detected:
                        invalids.append(
                            f"BEAT {beat.full_id}: {(polos, sangsih)[0].instrumenttype} P=[{''.join((n.symbol for n in beat.measures[(polos, sangsih)[0]].passes[DEFAULT].notes))}] S=[{orig_sangsih_str}]"
                        )
                    if autocorrected:
                        corrected_sangsih_str = "".join(
                            (n.symbol for n in beat.measures[(polos, sangsih)[1]].passes[DEFAULT].notes)
                        )
                        corrected.append(
                            f"BEAT {beat.full_id}: {(polos, sangsih)[0].instrumenttype} P=[{''.join((n.symbol for n in beat.measures[(polos, sangsih)[0]].passes[DEFAULT].notes))}] S=[{orig_sangsih_str}] -> S=[{corrected_sangsih_str}]"
                        )
        return invalids, corrected, ignored

    @override
    def _main(self) -> None:
        """Performs consistency checks and prints results.

        Args:
            score (Score): the score to analyze.
        """
        corrected_beat_lengths = []
        ignored_beat_lengths = []
        remaining_bad_beat_lengths = []

        corrected_measure_lengths = []
        ignored_measure_lengths = []
        remaining_bad_measure_lengths = []

        corrected_note_out_of_range = []
        ignored_note_out_of_range = []
        remaining_note_out_of_range = []

        corrected_invalid_kempyung = []
        ignored_invalid_kempyung = []
        remaining_incorrect_kempyung = []

        # pylint: disable=unused-variable
        corrected_incorrect_norot = []
        ignored_incorrect_norot = []
        remaining_incorrect_norot = []

        corrected_incorrect_ubitan = []
        ignored_incorrect_ubitan = []
        remaining_incorrect_ubitan = []
        # pylint: enable=unused-variable

        autocorrect = self.score.settings.options.notation_to_midi.autocorrect
        detailed_logging = self.score.settings.options.notation_to_midi.detailed_validation_logging

        if self.score.settings.instrumentgroup != InstrumentGroup.GONG_KEBYAR:
            self.logwarning("Skipping kempyung validation for non-gong kebyar scores.")

        gongan: Gongan
        for gongan in self.gongan_iterator(self.score):
            # Determine if the beat duration is a power of 2 (ignore kebyar)
            invalids, corrected, ignored = self._invalid_beat_lengths(gongan, autocorrect)
            remaining_bad_beat_lengths.extend(invalids)
            corrected_beat_lengths.extend(corrected)
            ignored_beat_lengths.extend(ignored)

            invalids, corrected, ignored = self._unequal_measure_lengths(
                gongan,
                beat_at_end=self.score.settings.notationfile.beat_at_end,
                autocorrect=autocorrect,
            )

            remaining_bad_measure_lengths.extend(invalids)
            corrected_measure_lengths.extend(corrected)
            ignored_measure_lengths.extend(ignored)

            invalids, corrected, ignored = self._out_of_range(gongan, autocorrect=autocorrect)
            remaining_note_out_of_range.extend(invalids)
            corrected_note_out_of_range.extend(corrected)
            ignored_note_out_of_range.extend(corrected)

            if (
                self.score.settings.instrumentgroup == InstrumentGroup.GONG_KEBYAR
                and self.score.settings.notationfile.autocorrect_kempyung
            ):
                invalids, corrected, ignored = self._incorrect_kempyung(gongan, autocorrect=autocorrect)
                remaining_incorrect_kempyung.extend(invalids)
                corrected_invalid_kempyung.extend(corrected)
                ignored_invalid_kempyung.extend(ignored)

        self.curr_gongan_id = None
        self.curr_measure_id = None

        def log_list(loglevel: callable, title: str, list: list[Any]) -> None:
            loglevel(title)
            for element in list:
                loglevel(f"    {str(element)}")

        def log_results(
            title_ok: str, title_error: str, corrected: list[Any], ignored: list[Any], remaining: list[Any]
        ) -> None:
            error = len(remaining) > 0
            warning = len(corrected) + len(ignored) > 0
            message = (
                title_ok
                if not error and not warning
                else f"{title_error}: corrected {len(corrected)}, ignored {len(ignored)}, remaining: {len(remaining)}"
            )
            if error:
                self.logerror(message)
            elif warning:
                self.logwarning(message)
            else:
                self.loginfo(message)
            if detailed_logging:
                if corrected:
                    self.logwarning(f"corrected:{corrected}")
                if ignored:
                    log_list(self.logger.warning, "ignored:", ignored)
            if remaining:
                log_list(self.logger.error, "remaining invalids:", remaining)

        log_results(
            "ALL BEAT LENGTHS ARE CORRECT",
            "INCORRECT BEAT LENGTHS",
            corrected_beat_lengths,
            ignored_beat_lengths,
            remaining_bad_beat_lengths,
        )
        log_results(
            "ALL MEASURES HAVE CORRECT LENGTH",
            "BEATS WITH UNEQUAL MEASURE LENGTHS",
            corrected_measure_lengths,
            ignored_measure_lengths,
            remaining_bad_measure_lengths,
        )
        log_results(
            "ALL NOTES ARE WITHIN THE INSTRUMENT RANGE",
            "BEATS WITH NOTES OUT OF INSTRUMENT RANGE",
            corrected_note_out_of_range,
            ignored_note_out_of_range,
            remaining_note_out_of_range,
        )
        log_results(
            "ALL KEMPYUNG PARTS ARE CORRECT",
            "INCORRECT KEMPYUNG",
            corrected_invalid_kempyung,
            ignored_invalid_kempyung,
            remaining_incorrect_kempyung,
        )

        return None
