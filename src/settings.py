from enum import StrEnum

from src.notation_classes import Source

BASE_NOTE_TIME = 24
MIDI_NOTES_DEF_FILE = "./settings/midinotes.csv"
BALIMUSIC4_DEF_FILE = "./settings/balimusic4font.csv"
TAGS_DEF_FILE = "./settings/instrumenttags.csv"

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


# instruments.csv
class InstrumentFields(StrEnum):
    POSITION = "position"
    INSTRUMENT = "instrument"
    GROUP = "groups"


# instrumenttags.csv
class InstrumentTagFields(StrEnum):
    TAG = "tag"
    INFILE = "infile"
    POSITION = "positions"


# midinotes.csv
class MidiNotesFields(StrEnum):
    INSTRUMENTGROUP = "instrumentgroup"
    INSTRUMENTTYPE = "instrumenttype"
    NOTEVALUE = "notevalue"
    MIDI = "midi"
    PIANOMIDI = "pianomidi"
