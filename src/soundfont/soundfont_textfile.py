"""Generates the content of the soundfont definition file.
Using a separate class for this makes it easy to create an other format
by creating another class.

Returns:
    _type_: _description_
"""

import os

from src.common.classes import MidiNote, Preset
from src.common.constants import InstrumentType, Position
from src.settings.classes import RunSettings
from src.soundfont.utils import sample_name_lookup, sample_notes_lookup, truncated_name

SampleFileName = str
SampleName = str


class SoundfontTextfile:
    content: str = ""
    type_to_midi_dict: dict[InstrumentType, list[MidiNote]]
    pos_to_midi_dict: dict[Position, list[MidiNote]]
    sample_name_lookup: dict[SampleFileName, SampleName]
    preset_dict: dict[Position, Preset]
    settings: RunSettings

    def __init__(
        self,
        midi_dict: dict[InstrumentType, list[MidiNote]],
        settings: RunSettings,
    ):
        self.type_to_midi_dict = {
            instr: [note for note in notes if note.sample]
            for instr, notes in midi_dict.items()
            if any(note.sample for note in notes)
        }
        self.pos_to_midi_dict = {
            pos: notes
            for i_type, notes in self.type_to_midi_dict.items()
            for pos in Position
            if pos.instrumenttype == i_type
        }
        self.preset_dict = Preset.get_preset_dict()
        self.settings = settings
        self.sample_name_lookup = sample_name_lookup(self.type_to_midi_dict)

    def _add_row(self, values: list[str]) -> None:
        # adds a new tab separated row containing the given values
        if self.content:
            self.content += "\n"
        self.content += "\t".join([str(val) for val in values])

    def _add_separator(self) -> None:
        # adds a separator row
        self.content += "\n"

    def _add_sample_section(self) -> None:
        # Generates the first section of the Soundfont definition
        self._add_row(["Samples", "Name", "Loop S-E", "Root key", "Correction", "File name", "Folder"])
        # Use the sample_note_lookup to make the list, in order to include each sample only once.
        # If multiple notes use the same sample, the root key is set here as the midinote value of the first note in the list.
        sample_note_lookup = sample_notes_lookup(self.type_to_midi_dict)
        for sample_file, sample_name in self.sample_name_lookup.items():
            self._add_row(["", sample_name, "", sample_note_lookup[sample_file][0].midinote, "", sample_file])
        self._add_row(["Search paths:", os.path.abspath(self.settings.samples.folder)])
        self._add_separator()

    def _add_instrument_section(self) -> None:
        # Generates the second section of the Soundfont definition
        self._add_row(["Instruments", "Name", "Generators"])
        for instrumentpos, midinotes in self.pos_to_midi_dict.items():
            self._add_row(["", instrumentpos])
            self._add_row(
                ["", "", "Sample name", "Global"] + [self.sample_name_lookup[midinote.sample] for midinote in midinotes]
            )
            self._add_row(
                ["", "", "Key Range", ""] + [f"{midinote.midinote}-{midinote.midinote}" for midinote in midinotes]
            )
            self._add_row(["", "", "Root Key", ""] + [midinote.midinote for midinote in midinotes])
        self._add_separator()

    def _add_preset_section(self) -> None:
        # Generates the third section of the Soundfont definition
        keys = {(preset.preset_name, preset.bank, preset.preset) for preset in self.preset_dict.values()}
        preset_dict = {
            key: [
                preset.position
                for preset in self.preset_dict.values()
                if (preset.preset_name, preset.bank, preset.preset) == key
            ]
            for key in keys
        }
        self._add_row(["Presets", "Name", "Generators", "Bank", "Preset"])
        for key, instruments in preset_dict.items():
            self._add_row(["", key[0], "", key[1], key[2]])
            self._add_row(["", "", "Instrument name", "Global"] + [instrument for instrument in instruments])
        self._add_row(["End of data"])
        self._add_separator()

    def create_soundfont_definition(self):
        # Generates the entire Soundfont definition content
        # This is the only method that should be called from outside this class.
        self._add_sample_section()
        self._add_instrument_section()
        self._add_preset_section()

    def save(self):
        outfilepath = self.settings.soundfont.def_filepath
        with open(outfilepath, "w") as outfile:
            outfile.write(self.content)
        return outfilepath
