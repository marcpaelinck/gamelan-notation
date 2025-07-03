from enum import StrEnum
from typing import Any, Literal

from src.common.constants import Modifier, ModifierType, Pitch, Position, Stroke
from src.common.notes import GenericNote, Note, NoteSymbol, Tone
from src.notation2midi.metadata_classes import MetaData
from src.notation2midi.rules.rules import Rule
from src.settings.classes import RunSettings
from src.settings.constants import ModifiersFields
from src.settings.settings import RunSettingsListener


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
        for notesymbol in notes:
            self.validate(notesymbol)

            attributes = notesymbol.model_dump() | {
                Note.Fields.OCTAVE: self.infer_octave(notesymbol),
                Note.Fields.NOTESYMBOL: notesymbol,
            }
            for modifier in [mod for mod in notesymbol.modifiers if mod is not Modifier.NONE]:
                mod_type, value = self.MODIFIER_DICT.get(modifier, None)
                if not mod_type:
                    raise ValueError("Unrecognized modifer %s" % modifier)
                match mod_type:
                    case ModifierType.STROKE:
                        attributes |= {Note.Fields.EFFECT: value}
                    case ModifierType.OCTAVE:
                        attributes |= {Note.Fields.OCTAVE: value}
                    case ModifierType.PATTERN:
                        attributes |= {Note.Fields.EFFECT: value, Note.Fields.PATTERN: []}
                    case ModifierType.VALUE:
                        attributes |= {Note.Fields.NOTE_VALUE: attributes[Note.Fields.NOTE_VALUE] * value}
                    case _:
                        raise ValueError("Unknown modifier type %s for %s" % (mod_type, modifier))
            if Note.Fields.EFFECT not in attributes:
                stroke = (
                    Stroke.NONE if attributes[Note.Fields.PITCH] in [Pitch.EXTENSION, Pitch.SILENCE] else Stroke.OPEN
                )
                attributes |= {Note.Fields.EFFECT: stroke}
            base_notes.append(GenericNote(**attributes))
        return base_notes
