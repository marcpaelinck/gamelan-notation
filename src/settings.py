from enum import StrEnum

from src.notation_classes import Source

BASE_NOTE_TIME = 24
MIDI_NOTES_DEF_FILE = "./settings/midinotes.csv"
NOTATIONFONT_DEF_FILE = "./settings/balimusic4font.csv"
TAGS_DEF_FILE = "./settings/instrumenttags.csv"
SOUNDFONT_FILE = "./settings/Gong Kebyar MP2.sf2"

CENDRAWASIH = Source(
    datapath=".\\data\\cendrawasih",
    infilename="Cendrawasih_complete.csv",
    outfilefmt="Cendrawasih {position}_{version}.{ext}",
)
MARGAPATI = Source(
    datapath=".\\data\\margapati", infilename="Margapati-UTF8.csv", outfilefmt="Margapati {position}_{version}.{ext}"
)
GENDINGANAK2 = Source(
    datapath=".\\data\\test",
    infilename="Gending Anak-Anak.csv",
    outfilefmt="Gending Anak-Anak {position}_{version}.{ext}",
)
DEMO = Source(datapath=".\\data\\test", infilename="demo.csv", outfilefmt="Demo {position}_{version}.{ext}")


# list of column headers used in the settings files

# balimusic4font.csv: Fields should correspond exactly with the Character class attributes


class SStrEnum(StrEnum):
    def __str__(self):
        return self.value


class FontFields(SStrEnum):
    SYMBOL = "symbol"
    UNICODE = "unicode"
    SYMBOL_DESCRIPTION = "symbol_description"
    BALIFONT_SYMBOL_DESCRIPTION = "balifont_symbol_description"
    SYMBOLVALUE = "value"
    DURATION = "duration"
    REST_AFTER = "rest_after"
    DESCRIPTION = "description"


# instruments.csv
class InstrumentFields(SStrEnum):
    POSITION = "position"
    INSTRUMENT = "instrument"
    GROUP = "groups"


# instrumenttags.csv
class InstrumentTagFields(SStrEnum):
    TAG = "tag"
    INFILE = "infile"
    POSITION = "positions"


# midinotes.csv
class MidiNotesFields(SStrEnum):
    INSTRUMENTGROUP = "instrumentgroup"
    INSTRUMENTTYPE = "instrumenttype"
    POSITIONS = "positions"
    SYMBOLVALUE = "notevalue"
    CHANNEL = "channel"
    MIDI = "midi"
