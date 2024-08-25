from enum import StrEnum

from src.common.classes import Source
from src.common.constants import InstrumentGroup, NotationFont

BASE_NOTE_TIME = 24
BASE_NOTES_PER_BEAT = 4
ATTENUATION_SECONDS_AFTER_MUSIC_END = 10  # additional time in seconds to let final chord attenuate.
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

SINOMLADRANG = Source(
    datapath=".\\data\\sinom ladrang",
    infilename="Sinom Ladrang_ubit4_font5.tsv",
    outfilefmt="Sinom Ladrang {position}_{version}.{ext}",
    font=NotationFont.BALIMUSIC5,
    instrumentgroup=InstrumentGroup.GONG_KEBYAR,
)
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
MARGAPATI4 = Source(
    datapath=".\\data\\margapati",
    infilename="Margapati_font4.tsv",
    outfilefmt="Margapati {position}_{version}.{ext}",
    font=NotationFont.BALIMUSIC4,
    instrumentgroup=InstrumentGroup.GONG_KEBYAR,
)
MARGAPATIREYONG3 = Source(
    datapath=".\\data\\margapati",
    infilename="Margapati reyong_font3.tsv",
    outfilefmt="Margapati {position}_{version}.{ext}",
    font=NotationFont.BALIMUSIC4,
    instrumentgroup=InstrumentGroup.GONG_KEBYAR,
)
MARGAPATI5 = Source(
    datapath=".\\data\\margapati",
    infilename="Margapati_font5.tsv",
    outfilefmt="Margapati {position}_{version}.{ext}",
    font=NotationFont.BALIMUSIC5,
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
    PITCH = "pitch"
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
    PITCH = "pitch"
    OCTAVE = "octave"
    STROKE = "stroke"
    REMARK = "remark"
    CHANNEL = "channel"
    MIDI = "midi"
