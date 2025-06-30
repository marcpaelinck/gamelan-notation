from typing import Any, ClassVar, override

from src.common.classes import Score
from src.common.constants import Position
from src.notation2midi.classes import Agent
from src.notation2midi.metadata_classes import MetaData
from src.notation2midi.rules.rule_cast_to_position import RuleCastToPosition
from src.notation2midi.rules.rule_process_modifiers import RuleProcessModifiers
from src.notation2midi.rules.rule_set_gracenote_octave import RuleSetGracenoteOctave
from src.notation2midi.rules.rules import Rule
from src.settings.classes import RunSettings


class RulesEngine:
    _RULES: ClassVar[list[Rule]] = [RuleProcessModifiers, RuleCastToPosition, RuleSetGracenoteOctave]

    def __init__(self, run_settings: RunSettings):
        self.run_settings = run_settings

    def execute(self, notes: list[Any], position: Position, all_positions: list[Position], metadata: list[MetaData]):
        for rule in self._RULES:
            notes = rule(run_settings=self.run_settings).fire(
                notes=notes, position=position, all_positions=all_positions, metadata=metadata
            )
        return notes


class RulesAgent(Agent):
    """Casts generic notes to specific instruments by applying instrument rules, and returns
       a Score object containing BoundNotes: notes that are bound to a specific instrument position.
        - Splits staves having multiple instrument position tags into staves for individual positions.
        - Updates the octave of grace notes.
    also updateS grace note octaves"""

    LOGGING_MESSAGE = "APPLYING RULES"
    EXPECTED_INPUT_TYPES = (Agent.InputOutputType.GENERICSCORE,)
    RETURN_TYPE = Agent.InputOutputType.BOUNDSCORE

    score: Score

    def __init__(self, generic_score: Score):
        super().__init__(generic_score.settings)
        self.score = generic_score

    @override
    @classmethod
    def run_condition_satisfied(cls, run_settings: RunSettings):
        return True

    # def _note_from_rec(
    #     self,
    #     note: GenericNote,
    #     position: Position,
    #     all_positions: list[Position],
    #     metadata: list[MetaData],
    # ) -> Note:
    #     """Casts the given NoteRecord object to a Note object which is bound to a Position.
    #     If multiple positions share the same notation this method applies rules
    #     (e.g. octavation or kempyung) to cast the NoteRecord to the correct Note for the given position.
    #     Args:
    #         symbol (str): notation characters.
    #         position (Position): position to match.
    #         unisono_positions (list[Position]): positions that share the same notation.
    #     Returns:
    #         Note: _description_
    #     """
    #     if len(all_positions) == 1:
    #         # Notation for single position
    #         if position not in all_positions:
    #             raise ValueError(f"{position} not in list {all_positions}")
    #         note = NoteFactory.get_bound_note(
    #             position=position,
    #             pitch=note.pitch,
    #             octave=note.octave,
    #             stroke=note.stroke,
    #             duration=note.duration,
    #             rest_after=note.rest_after,
    #         )
    #         if not note:
    #             # Most common error is wrong octave. Find similar symbols with the correct octave.
    #             any_oct_symbol = note.symbol + ",<"
    #             alternatives = [
    #                 n.symbol
    #                 for n in NoteFactory.VALIDNOTES
    #                 if n.position is position and all(char in any_oct_symbol for char in n.symbol)
    #             ]
    #             msg1 = "Invalid note '%s' for %s." % (note.symbol, position)
    #             msg2 = " Did you mean '%s'?" % ("or '".join(alternatives)) if alternatives else ""
    #             raise ValueError(msg1 + msg2)
    #         return note

    #     # The notation is for multiple positions. Determine pitch and octave using the 'unisono rules'.

    #     # Create a Tone object from the the symbol by finding any matching note (disregarding the position)
    #     # TODO move to RulesApplicationAgent
    #     reference_tone = Tone(pitch=note.pitch, octave=note.octave)
    #     tone = RulesEngine.cast_to_position(
    #         tone=reference_tone, position=position, all_positions=set(all_positions), metadata=metadata
    #     )

    #     # Return the matching note within the position's range
    #     if tone:
    #         note = Note(
    #             position=position,
    #             pitch=tone.pitch,
    #             octave=tone.octave,
    #             stroke=note.stroke,
    #             duration=note.duration,
    #             rest_after=note.rest_after,
    #         )
    #         return note.model_copy_x(transformation=tone.transformation)
    #     else:
    #         # return silence
    #         note = Note(
    #             position=position,
    #             pitch=Pitch.NONE,
    #             octave=None,
    #             stroke=Stroke.SILENCE,
    #             duration=0,
    #             rest_after=note.duration + note.rest_after,
    #         )
    #         return note
    #         # raise ValueError("Could not find an equivalent for %s for %s}" % (note_record.symbol, position))

    # def _convert_to_notes(
    #     self,
    #     noterecord_list: list[GenericNote],
    #     position: Position,
    #     all_positions: list[Position],
    #     metadata: list[MetaData],
    # ) -> list[Note]:
    #     """Converts the GenericNote objects to position bound Note objects.
    #         Applies rules to transform the note to the correct value for the given position (e.g. kempyung, octavation).
    #         Updates the octave of grace notes.
    #         Converts tremolo notes to a pattern of Note objects.

    #        If the stave stands for multiple reyong positions, the notation is transformed to match
    #        each position separately. There are two possible cases:
    #         - REYONG_1 and REYONG_3 are combined: the notation is expected to represent the REYONG_1 part
    #           and the score is octavated for the REYONG_3 position.
    #         - REYONG_2 and REYONG_4: similar case. The notation should represent the REYONG_2 part.
    #         - All reyong positions: the notation is expected to represent the REYONG_1 part.
    #           In this case the kempyung equivalent of the notation will be determined for REYONG_2
    #           and REYONG_4 within their respective range.

    #     Args:
    #         stave (str): one stave of notation
    #         position (Position):
    #         multiple_positions (list[Position]): List of all positions for this stave.

    #     Returns: str | None: _description_
    #     """
    #     notes = []  # will contain the Note objects
    #     for note_rec in noterecord_list:
    #         next_note = None
    #         try:
    #             next_note = self._note_from_rec(note_rec, position, all_positions, metadata=metadata)
    #         except ValueError as e:
    #             self.logerror(str(e))
    #         if not next_note:
    #             self.logerror(f"Could not cast {note_rec.symbol} to {position.value}")
    #         else:
    #             notes.append(next_note)

    #     return notes

    @override
    def _main(self):
        rules_engine = RulesEngine(self.run_settings)
        for gongan in self.gongan_iterator(self.score):
            for beat in self.beat_iterator(gongan):
                for position, measure in beat.measures.items():
                    for pass_ in self.pass_iterator(measure):
                        bound_notes = rules_engine.execute(
                            notes=pass_.generic_notes,
                            position=position,
                            all_positions=measure.all_positions,
                            metadata=gongan.metadata,
                        )
                        pass_.notes = bound_notes
        return self.score
