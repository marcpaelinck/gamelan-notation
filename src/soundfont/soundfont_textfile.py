import os

from src.common.classes import MidiNote, Preset, RunSettings
from src.common.constants import InstrumentType, MidiDict
from src.soundfont.utils import sample_name


class SoundfontTextfile:
    content: str = ""
    midi_dict: dict[InstrumentType, list[MidiNote]]
    preset_dict: dict[InstrumentType, Preset]
    settings: RunSettings

    def __init__(
        self,
        midi_dict: dict[InstrumentType, list[MidiNote]],
        preset_dict: dict[InstrumentType, Preset],
        settings: RunSettings,
    ):
        self.midi_dict = {
            instr: [note for note in notes if note.sample]
            for instr, notes in midi_dict.items()
            if any(note.sample for note in notes)
        }
        self.preset_dict = {instr: preset for instr, preset in preset_dict.items() if instr in self.midi_dict.keys()}
        self.settings = settings

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
        for midinotes in self.midi_dict.values():
            for midinote in midinotes:
                self._add_row(["", sample_name(midinote), "", midinote.midinote, "", midinote.sample])
        self._add_row(["Search paths:", os.path.abspath(self.settings.samples.folder)])
        self._add_separator()

    def _add_instrument_section(self) -> None:
        # Generates the second section of the Soundfont definition
        self._add_row(["Instruments", "Name", "Generators"])
        for instrumenttype, midinotes in self.midi_dict.items():
            self._add_row(["", instrumenttype])
            self._add_row(["", "", "Sample name", "Global"] + [sample_name(midinote) for midinote in midinotes])
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
                preset.instrumenttype
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
        outfilepath = self.settings.soundfont.filepath.format(midiversion=self.settings.midi.midiversion)
        path_without_ext, ext = os.path.splitext(outfilepath)
        outfilepath = path_without_ext + ".txt"
        with open(outfilepath, "w") as outfile:
            outfile.write(self.content)
        return outfilepath
