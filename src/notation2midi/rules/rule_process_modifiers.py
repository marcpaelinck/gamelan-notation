from enum import StrEnum
from typing import Any, Literal

from src.common.constants import Modifier, ModifierType, Pitch, Position, Stroke
from src.common.notes import GenericNote, NoteSymbol, Tone
from src.notation2midi.metadata_classes import MetaData
from src.notation2midi.rules.rules import Rule
from src.settings.classes import RunSettings
from src.settings.constants import ModifiersFields
from src.settings.settings import RunSettingsListener


class NoteFields(StrEnum):
    PITCH = "pitch"
    OCTAVE = "octave"
    EFFECT = "effect"
    PATTERN = "pattern"
    NOTE_VALUE = "note_value"
    GENERIC_NOTE = "generic_note"
    SYMBOL = "symbol"
    MODIFIERS = "modifiers"


class RuleProcessModifiers(Rule, RunSettingsListener):
    NAME = "Process modifier symbols (converts NoteSymbol instances to GenericNote instances)"
    MODIFIER_DICT = dict[Modifier, tuple[ModifierType, Any]]

    @classmethod
    def cls_initialize(cls, run_settings: RunSettings):
        cls.MODIFIER_DICT = {
            row[ModifiersFields.MODIFIER]: (row[ModifiersFields.MOD_TYPE], row[ModifiersFields.VALUE])
            for row in run_settings.data.modifiers
        }

    @classmethod
    def validate(cls, note: NoteSymbol) -> bool:
        return True

    @classmethod
    def infer_octave(cls, note: NoteSymbol) -> Literal[0, 1, 2, None]:
        return (
            None
            if note.pitch not in Tone.MELODIC_PITCHES
            else 2 if Modifier.OCTAVE_2 in note.modifiers else 0 if Modifier.OCTAVE_0 in note.modifiers else 1
        )

    def fire(
        self, notes: list[NoteSymbol], position: Position, all_positions: list[Position], metadata: list[MetaData]
    ) -> list[GenericNote]:
        base_notes: list[GenericNote] = []
        for generic_note in notes:
            self.validate(generic_note)

            attributes = generic_note.model_dump() | {
                NoteFields.OCTAVE: self.infer_octave(generic_note),
                NoteFields.GENERIC_NOTE: generic_note,
            }
            for modifier in [mod for mod in generic_note.modifiers if mod is not Modifier.NONE]:
                mod_type, value = self.MODIFIER_DICT.get(modifier, None)
                if not mod_type:
                    raise ValueError("Unrecognized modifer %s" % modifier)
                match mod_type:
                    case ModifierType.STROKE:
                        attributes |= {NoteFields.EFFECT: value}
                    case ModifierType.OCTAVE:
                        attributes |= {NoteFields.OCTAVE: value}
                    case ModifierType.PATTERN:
                        attributes |= {NoteFields.EFFECT: value, NoteFields.PATTERN: []}
                    case ModifierType.VALUE:
                        attributes |= {NoteFields.NOTE_VALUE: attributes[NoteFields.NOTE_VALUE] * value}
                    case _:
                        raise ValueError("Unknown modifier type %s for %s" % (mod_type, modifier))
            if NoteFields.EFFECT not in attributes:
                stroke = (
                    Stroke.NONE if attributes[NoteFields.PITCH] in [Pitch.EXTENSION, Pitch.SILENCE] else Stroke.OPEN
                )
                attributes |= {NoteFields.EFFECT: stroke}
            base_notes.append(GenericNote(**attributes))
        return base_notes
