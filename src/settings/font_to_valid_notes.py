from itertools import product
from typing import Any, Union

from pydantic import BaseModel, ConfigDict

from src.common.constants import (
    InstrumentType,
    Modifier,
    PatternType,
    Pitch,
    Position,
    Stroke,
)
from src.settings.classes import RunSettings
from src.settings.constants import (
    EffectsFields,
    FontFields,
    InstrumentFields,
    ModifiersFields,
    NoteFields,
)


class ValidNote(BaseModel):
    # Class used to create notes with validated field values. Only int values may be None,
    # other values will raise an exception if missing, malformed or None (we use Pydantic to check this).
    # We don't use the src.common.notes.Note class here to avoid circular references.
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")

    instrumenttype: InstrumentType
    position: Position
    symbol: str
    pitch: Pitch
    octave: int | None
    effect: Union[Stroke, PatternType]
    note_value: float | None


class ValidNoteGenerator:
    """This class is used to generates a list of ValidNote 'records' that represents all valid combinations
    of the ValidNote attributes. Method get_valid_note_records returns this list."""

    def __init__(self, run_settings: RunSettings):
        """Retrieve font and instrument config data"""
        self.run_settings = run_settings
        self.font_sorting_order = {
            sym[FontFields.SYMBOL]: (
                count
                if sym[FontFields.PITCH] is not Pitch.NONE
                else 100 * list(Modifier).index(sym[FontFields.MODIFIER])
            )
            for count, sym in enumerate(run_settings.data.font)
        }
        self.instrument_data = [
            rec for rec in self.run_settings.data.instruments.filterOn(self.run_settings.instrumentgroup)
        ]
        self.effect_dict = {
            rec[EffectsFields.EFFECT]: rec[EffectsFields.PITCHES] for rec in self.run_settings.data.effects
        }
        self.property_to_modifier_dict = {
            (rec[ModifiersFields.NOTE_ATTRIBUTE], rec[ModifiersFields.VALUE]): rec[ModifiersFields.MODIFIER]
            for rec in self.run_settings.data.modifiers
        }
        self.font_table = self.run_settings.data.font

    def normalize_symbol(self, symbol: str) -> str:
        """Returns the note symbol with the characters ordered in a normalized sequence"""
        return "".join(sorted(symbol, key=lambda c: self.font_sorting_order.get(c, 99)))

    def find_font_character(self, properties: list[tuple[NoteFields, Stroke | PatternType | int | float]]) -> str:
        """Returns the single-character symbol that corresponds with the given combination of properties.
        Returns an empty string if not found."""
        return next(
            (rec[FontFields.SYMBOL] for rec in self.font_table if all(rec[prop[0]] == prop[1] for prop in properties)),
            "",
        )

    def get_note_symbol(
        self, pitch: Pitch = None, octave: int = None, effect: Stroke | PatternType = None, note_value: float = None
    ) -> str:
        """Returns the font's character combination for the given note properties. raises a ValueError if not found."""

        # Determine the modifier values that correspond with the given note properties.
        modifiers = [
            self.property_to_modifier_dict.get(property, None)
            for property in [
                (NoteFields.OCTAVE, octave),
                (NoteFields.EFFECT, effect),
                (NoteFields.NOTE_VALUE, note_value),
            ]
            if self.property_to_modifier_dict.get(property, None)
        ]

        # Look up the pitch and modifier values in the font table and retrieve the corresponding character values.
        symbol = ""
        char = ""
        # First try a combination of pitch and modifier (e.g. in case of GRACE_NOTE)
        for modifier in modifiers:
            if char := self.find_font_character([(FontFields.PITCH, pitch), (FontFields.MODIFIER, modifier)]):
                modifiers.remove(modifier)
                break
        symbol += char

        # Match the pitch if not yet matched
        if not symbol:
            if not (
                char := self.find_font_character([(FontFields.PITCH, pitch), (FontFields.MODIFIER, Modifier.NONE)])
            ):
                raise ValueError("Pitch %s not found in font table" % pitch)
            symbol += char

        # Now match the remaining modifiers
        while modifiers:
            modifier = modifiers.pop()
            if not (char := self.find_font_character([(FontFields.MODIFIER, modifier)])):
                raise ValueError("Modifier %s not found in font table" % modifier)
            symbol += char
        return self.normalize_symbol(symbol)

    def get_valid_note_records(self) -> list[dict[str, Any]]:
        """Returns a list of all possible ValidNote instances."""
        note_list = []

        for record in self.instrument_data:
            instrumenttype = record[InstrumentFields.INSTRUMENTTYPE]
            position: Position = record[InstrumentFields.POSITION]
            tones = {tone for tone in record[InstrumentFields.TONES] + record[InstrumentFields.EXTENDED_TONES]}
            strokes = set(record[InstrumentFields.STROKES])
            grace_stroke = {Stroke.GRACE_NOTE} if Stroke.GRACE_NOTE in strokes else set()
            patterns = set(record[InstrumentFields.PATTERNS])
            rests = list(product(record[InstrumentFields.RESTS], [None]))

            valid_melodics = product(tones, strokes - grace_stroke, [1.0, 0.5, 0.25])
            valid_grace = product(tones, grace_stroke, [0.0])
            valid_patterns = product(tones, patterns, [1.0])
            valid_rests = product(rests, [Stroke.NONE], [1.0, 0.5, 0.25])

            # Strokes (OPEN, ABBREVIATED, MUTED)
            # TODO grace_notes are excluded here and included in the next section. Is there a more elegant way to
            #  treat grace notes separately?
            for valid_combinations in (valid_melodics, valid_grace, valid_patterns, valid_rests):
                for (pitch, octave), effect, note_value in valid_combinations:
                    if not effect in self.effect_dict or pitch in self.effect_dict[effect]:
                        note_list.append(
                            ValidNote(
                                instrumenttype=instrumenttype,
                                position=position,
                                symbol=self.get_note_symbol(
                                    pitch=pitch, octave=octave, effect=effect, note_value=note_value
                                ),
                                pitch=pitch,
                                octave=octave,
                                effect=effect,
                                note_value=note_value,
                                # modifier=Modifier.NONE,
                            ).model_dump()
                        )

        return note_list
