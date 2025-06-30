from typing import Any

from src.common.constants import Modifier, ModifierType, Position
from src.common.notes import BaseNote, GenericNote, Note, NoteFactory
from src.notation2midi.metadata_classes import MetaData
from src.notation2midi.rules.rules import Rule
from src.settings.classes import RunSettings
from src.settings.settings import RunSettingsListener


class RuleProcessModifiers(Rule, RunSettingsListener):
    NAME = "Process modifier symbols"
    MODIFIER_DICT = dict[Modifier, tuple[ModifierType, Any]]

    @classmethod
    def cls_initialize(cls, run_settings: RunSettings):
        cls.MODIFIER_DICT = {row["modifier"]: (row["mod_type"], row["value"]) for row in run_settings.data.modifiers}

    def fire(
        self, notes: list[GenericNote], position: Position, all_positions: list[Position], metadata: list[MetaData]
    ) -> list[BaseNote]:
        base_notes: list[Note] = []
        for generic_note in notes:
            base_note = BaseNote(
                pitch=generic_note.pitch,
                octave=generic_note.octave,
                note_value=1,
                generic_note=generic_note,
            )
            for modifier in [mod for mod in generic_note.modifiers if mod is not Modifier.NONE]:
                mod_type, value = self.MODIFIER_DICT.get(modifier, None)
                if not mod_type:
                    raise ValueError("Unrecognized modifer %s" % modifier)
                match mod_type:
                    case ModifierType.STROKE:
                        base_note = NoteFactory.clone_base_note(base_note, stroke=value)
                    case ModifierType.OCTAVE:
                        base_note = NoteFactory.clone_base_note(base_note, octave=value)
                    case ModifierType.PATTERN:
                        base_note = NoteFactory.create_pattern(base_note, patterntype=value)
                    case ModifierType.VALUE:
                        base_note = NoteFactory.clone_base_note(base_note, note_value=value)
                    case _:
                        raise ValueError("Unknown modifier type %s for %s" % (mod_type, modifier))
            base_notes.append(base_note)
        return base_notes
