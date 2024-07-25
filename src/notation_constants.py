import codecs
from enum import Enum, auto

INSTRUMENT = str
BPM = int
PASS = int
DEFAULT = -1


class InstrumentGroup(Enum):
    GONG_KEBYAR = auto()
    SEMAR_PAGULINGAN = auto()


class InstrumentType(Enum):
    GONGS = auto()
    KEMPLI = auto()
    CENGCENG = auto()
    KENDANG = auto()
    JEGOGAN = auto()
    CALUNG = auto()
    PENYACAH = auto()
    PEMADE = auto()
    KANTILAN = auto()
    UGAL = auto()
    GENDERRAMBAT = auto()
    REYONG = auto()
    TROMPONG = auto()


class NoteValue(Enum):
    DING0 = auto()
    DONG0 = auto()
    DENG0 = auto()
    DEUNG0 = auto()
    DUNG0 = auto()
    DANG0 = auto()
    DAING0 = auto()
    DING1 = auto()
    DONG1 = auto()
    DENG1 = auto()
    DEUNG1 = auto()
    DUNG1 = auto()
    DANG1 = auto()
    DAING1 = auto()
    DING2 = auto()
    DONG2 = auto()
    DENG2 = auto()
    DEUNG2 = auto()
    DUNG2 = auto()
    DANG2 = auto()
    DAING2 = auto()
    DING0_MUTED = auto()
    DONG0_MUTED = auto()
    DENG0_MUTED = auto()
    DEUNG0_MUTED = auto()
    DUNG0_MUTED = auto()
    DANG0_MUTED = auto()
    DAING0_MUTED = auto()
    DING1_MUTED = auto()
    DONG1_MUTED = auto()
    DENG1_MUTED = auto()
    DEUNG1_MUTED = auto()
    DUNG1_MUTED = auto()
    DANG1_MUTED = auto()
    DAING1_MUTED = auto()
    DING2_MUTED = auto()
    DONG2_MUTED = auto()
    DENG2_MUTED = auto()
    DEUNG2_MUTED = auto()
    DUNG2_MUTED = auto()
    DANG2_MUTED = auto()
    DAING2_MUTED = auto()
    GIR = auto()
    PUR = auto()
    TONG = auto()
    KEP = auto()
    PAK = auto()
    DUT = auto()
    TUT = auto()
    KRUM = auto()
    PUNG = auto()
    BYONG = auto()
    BYOT = auto()
    JET = auto()
    TICK_1_PANGGUL = auto()
    TICK_2_PANGGUL = auto()
    KAP = auto()
    PEK = auto()
    DAG = auto()
    DUG = auto()
    TAK = auto()
    TEK = auto()
    PLAK = auto()
    MUTED = auto()
    OPEN = auto()
    MODIFIER_PREV1 = auto()
    MODIFIER_PREV2 = auto()
    SILENCE = auto()
    EXTENSION = auto()
    NOT_IMPLEMENTED = auto()

    @property
    def isnote(self):
        non_notes = [
            self.MODIFIER_PREV1,
            self.MODIFIER_PREV2,
            self.SILENCE,
            self.EXTENSION,
            self.NOT_IMPLEMENTED,
        ]
        return self not in non_notes


TAG_TO_INSTRUMENTTYPE_DICT = {
    "gangsa p": InstrumentType.PEMADE,
    "gangsa s": InstrumentType.PEMADE,
    "ugal": InstrumentType.UGAL,
    "gying": InstrumentType.UGAL,
}

# MIDI to Notation

MIDI_TO_COURIER = {
    36: "\u1ECD",
    37: "\u1EB9",
    38: "\u1EE5",
    39: "\u1EA1",
    40: "\u0131",
    41: "o",
    42: "e",
    43: "u",
    44: "a",
    45: "i",
}
VALID_MIDI_MESSAGE_TYPES = ["note_on", "note_off", "rest"]

TO_PIANO = {36: 53, 37: 55, 38: 59, 39: 60, 40: 64, 41: 65, 42: 67, 43: 71, 44: 72, 45: 76}
FROM_PIANO = {53: 36, 55: 37, 59: 38, 60: 39, 64: 40, 65: 41, 67: 42, 71: 43, 72: 44, 76: 45}
