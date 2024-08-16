from enum import StrEnum

from src.common.classes import Source
from src.common.constants import InstrumentGroup, NotationFont

BASE_NOTE_TIME = 24
MIDI_NOTES_DEF_FILE = "./settings/midinotes.tsv"
NOTATIONFONT_DEF_FILES = {
    NotationFont.BALIMUSIC4: "./settings/balimusic4font.tsv",
    NotationFont.BALIMUSIC5: "./settings/balimusic5font.tsv",
}
TAGS_DEF_FILE = "./settings/instrumenttags.tsv"
SOUNDFONT_FILE = "./settings/Gong Kebyar MP2.sf2"

METADATA = "metadata"
COMMENT = "comment"
NON_INSTRUMENT_TAGS = [METADATA, COMMENT]

CENDRAWASIH = Source(
    datapath=".\\data\\cendrawasih",
    infilename="Cendrawasih_complete.tsv",
    outfilefmt="Cendrawasih {position}_{version}.{ext}",
    font=NotationFont.BALIMUSIC4,
    instrumentgroup=InstrumentGroup.GONG_KEBYAR,
)
CENDRAWASIH5 = Source(
    datapath=".\\data\\cendrawasih",
    infilename="Cendrawasih_complete_font5.tsv",
    outfilefmt="Cendrawasih {position}_{version}.{ext}",
    font=NotationFont.BALIMUSIC5,
    instrumentgroup=InstrumentGroup.GONG_KEBYAR,
)
MARGAPATI = Source(
    datapath=".\\data\\margapati",
    infilename="Margapati-UTF8.tsv",
    outfilefmt="Margapati {position}_{version}.{ext}",
    font=NotationFont.BALIMUSIC4,
    instrumentgroup=InstrumentGroup.GONG_KEBYAR,
)
GENDINGANAK2 = Source(
    datapath=".\\data\\test",
    infilename="Gending Anak-Anak.tsv",
    outfilefmt="Gending Anak-Anak {position}_{version}.{ext}",
    font=NotationFont.BALIMUSIC4,
    instrumentgroup=InstrumentGroup.GONG_KEBYAR,
)
DEMO = Source(
    datapath=".\\data\\test",
    infilename="demo.tsv",
    outfilefmt="Demo {position}_{version}.{ext}",
    font=NotationFont.BALIMUSIC4,
    instrumentgroup=InstrumentGroup.GONG_KEBYAR,
)


# list of column headers used in the settings files

# balimusic4font.tsv: Fields should correspond exactly with the Character class attributes


class SStrEnum(StrEnum):
    def __str__(self):
        return self.value


class FontFields(SStrEnum):
    SYMBOL = "symbol"
    UNICODE = "unicode"
    SYMBOL_DESCRIPTION = "symbol_description"
    BALIFONT_SYMBOL_DESCRIPTION = "balifont_symbol_description"
    NOTE = "note"
    OCTAVE = "octave"
    STROKE = "stroke"
    DURATION = "duration"
    REST_AFTER = "rest_after"
    DESCRIPTION = "description"


# instruments.tsv
class InstrumentFields(SStrEnum):
    POSITION = "position"
    INSTRUMENT = "instrument"
    GROUP = "groups"


# instrumenttags.tsv
class InstrumentTagFields(SStrEnum):
    TAG = "tag"
    INFILE = "infile"
    POSITION = "positions"


# midinotes.tsv
class MidiNotesFields(SStrEnum):
    INSTRUMENTGROUP = "instrumentgroup"
    INSTRUMENTTYPE = "instrumenttype"
    POSITIONS = "positions"
    NOTE = "note"
    OCTAVE = "octave"
    STROKE = "stroke"
    CHANNEL = "channel"
    MIDI = "midi"
