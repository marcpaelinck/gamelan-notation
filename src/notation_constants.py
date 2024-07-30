from enum import Enum, StrEnum, auto

BPM = int
PASS = int
DEFAULT = -1


class InstrumentGroup(StrEnum):
    GONG_KEBYAR = "GONG_KEBYAR"
    SEMAR_PAGULINGAN = "SEMAR_PAGULINGAN"
    GONG_PELEGONGAN = "GONG_PELEGONGAN"
    GENDER_WAYANG = "GENDER_WAYANG"


class InstrumentType(StrEnum):
    GONGS = "GONGS"
    KEMPLI = "KEMPLI"
    CENGCENG = "CENGCENG"
    KENDANG = "KENDANG"
    JEGOGAN = "JEGOGAN"
    CALUNG = "CALUNG"
    PENYACAH = "PENYACAH"
    PEMADE = "PEMADE"
    KANTILAN = "KANTILAN"
    UGAL = "UGAL"
    GENDERRAMBAT = "GENDERRAMBAT"
    GENDERWAYANG = "GENDERWAYANG"
    REYONG = "REYONG"
    TROMPONG = "TROMPONG"

    def __repr__(self):
        # Enables to decode list of values
        return self.value


class InstrumentPosition(StrEnum):
    UGAL = "UGAL"
    GENDERRAMBAT = "GENDERRAMBAT"
    TROMPONG = "TROMPONG"
    PEMADE_POLOS = "PEMADE_POLOS"
    PEMADE_SANGSIH = "PEMADE_SANGSIH"
    KANTILAN_POLOS = "KANTILAN_POLOS"
    KANTILAN_SANGSIH = "KANTILAN_SANGSIH"
    REYONG_1 = "REYONG_1"
    REYONG_2 = "REYONG_2"
    REYONG_3 = "REYONG_3"
    REYONG_4 = "REYONG_4"
    CALUNG = "CALUNG"
    JEGOGAN = "JEGOGAN"
    PENYACAH = "PENYACAH"
    CENGCENG = "CENGCENG"
    KENDANG = "KENDANG"
    KEMPLI = "KEMPLI"
    GONGS = "GONGS"
    GENDERWAYANG_POLOS = "GENDERWAYANG_POLOS"
    GENDERWAYANG_SANGSIH = "GENDERWAYANG_SANGSIH"

    def __repr__(self):
        # Enables to decode list of values
        return self.value

    @property
    def instrumenttype(self):
        return InstrumentType[self.split("_")[0]]


class NoteType(StrEnum):
    MELODIC = "MELODIC"
    PERCUSSION = "PERCUSSION"


class MutingType(StrEnum):
    OPEN = auto()
    MUTED = auto()


class Note(Enum):
    DING = "DING", NoteType.MELODIC, auto()
    DONG = "DONG", NoteType.MELODIC, auto()
    DENG = "DENG", NoteType.MELODIC, auto()
    DEUNG = "DEUNG", NoteType.MELODIC, auto()
    DUNG = "DUNG", NoteType.MELODIC, auto()
    DANG = "DANG", NoteType.MELODIC, auto()
    DAING = "DAING", NoteType.MELODIC, auto()
    BYONG = "BYONG", NoteType.PERCUSSION, auto()
    BYOT = "BYOT", NoteType.PERCUSSION, auto()
    DAG = "DAG", NoteType.PERCUSSION, auto()
    DUG = "DUG", NoteType.PERCUSSION, auto()
    DUT = "DUT", NoteType.PERCUSSION, auto()
    GIR = "GIR", NoteType.PERCUSSION, auto()
    JET = "JET", NoteType.PERCUSSION, auto()
    KAP = "KAP", NoteType.PERCUSSION, auto()
    KEP = "KEP", NoteType.PERCUSSION, auto()
    KRUM = "KRUM", NoteType.PERCUSSION, auto()
    MUTED = "MUTED", NoteType.PERCUSSION, auto()
    OPEN = "OPEN", NoteType.PERCUSSION, auto()
    PAK = "PAK", NoteType.PERCUSSION, auto()
    PEK = "PEK", NoteType.PERCUSSION, auto()
    PLAK = "PLAK", NoteType.PERCUSSION, auto()
    PUNG = "PUNG", NoteType.PERCUSSION, auto()
    PUR = "PUR", NoteType.PERCUSSION, auto()
    TAK = "TAK", NoteType.PERCUSSION, auto()
    TEK = "TEK", NoteType.PERCUSSION, auto()
    TICK = "TICK", NoteType.PERCUSSION, auto()
    TONG = "TONG", NoteType.PERCUSSION, auto()
    TUT = "TUT", NoteType.PERCUSSION, auto()

    def __init__(self, notename: str, notetype: NoteType, sequence: int):
        self._value_ = notename
        self.type = notetype
        self.sequence = sequence

    def __repr__(self):
        return self.value

    def __str__(self):
        return self.value


class SymbolValue(Enum):
    # 0=lower instrument octave, 1=central instrument octave, 2=higher instrument octave.
    # The octave numbering is relative to the instrument's range.
    DING0 = "DING0", Note.DING, 0, MutingType.OPEN, auto()
    DONG0 = "DONG0", Note.DONG, 0, MutingType.OPEN, auto()
    DENG0 = "DENG0", Note.DENG, 0, MutingType.OPEN, auto()
    DEUNG0 = "DEUNG0", Note.DEUNG, 0, MutingType.OPEN, auto()
    DUNG0 = "DUNG0", Note.DUNG, 0, MutingType.OPEN, auto()
    DANG0 = "DANG0", Note.DANG, 0, MutingType.OPEN, auto()
    DAING0 = "DAING0", Note.DAING, 0, MutingType.OPEN, auto()
    DING1 = "DING1", Note.DING, 1, MutingType.OPEN, auto()
    DONG1 = "DONG1", Note.DONG, 1, MutingType.OPEN, auto()
    DENG1 = "DENG1", Note.DENG, 1, MutingType.OPEN, auto()
    DEUNG1 = "DEUNG1", Note.DEUNG, 1, MutingType.OPEN, auto()
    DUNG1 = "DUNG1", Note.DUNG, 1, MutingType.OPEN, auto()
    DANG1 = "DANG1", Note.DANG, 1, MutingType.OPEN, auto()
    DAING1 = "DAING1", Note.DAING, 1, MutingType.OPEN, auto()
    DING2 = "DING2", Note.DING, 2, MutingType.OPEN, auto()
    DONG2 = "DONG2", Note.DONG, 2, MutingType.OPEN, auto()
    DENG2 = "DENG2", Note.DENG, 2, MutingType.OPEN, auto()
    DEUNG2 = "DEUNG2", Note.DEUNG, 2, MutingType.OPEN, auto()
    DUNG2 = "DUNG2", Note.DUNG, 2, MutingType.OPEN, auto()
    DANG2 = "DANG2", Note.DANG, 2, MutingType.OPEN, auto()
    DAING2 = "DAING2", Note.DAING, 2, MutingType.OPEN, auto()
    DING0_MUTED = "DING0_MUTED", Note.DING, 0, MutingType.MUTED, auto()
    DONG0_MUTED = "DONG0_MUTED", Note.DONG, 0, MutingType.MUTED, auto()
    DENG0_MUTED = "DENG0_MUTED", Note.DENG, 0, MutingType.MUTED, auto()
    DEUNG0_MUTED = "DEUNG0_MUTED", Note.DEUNG, 0, MutingType.MUTED, auto()
    DUNG0_MUTED = "DUNG0_MUTED", Note.DUNG, 0, MutingType.MUTED, auto()
    DANG0_MUTED = "DANG0_MUTED", Note.DANG, 0, MutingType.MUTED, auto()
    DAING0_MUTED = "DAING0_MUTED", Note.DAING, 0, MutingType.MUTED, auto()
    DING1_MUTED = "DING1_MUTED", Note.DING, 1, MutingType.MUTED, auto()
    DONG1_MUTED = "DONG1_MUTED", Note.DONG, 1, MutingType.MUTED, auto()
    DENG1_MUTED = "DENG1_MUTED", Note.DENG, 1, MutingType.MUTED, auto()
    DEUNG1_MUTED = "DEUNG1_MUTED", Note.DEUNG, 1, MutingType.MUTED, auto()
    DUNG1_MUTED = "DUNG1_MUTED", Note.DUNG, 1, MutingType.MUTED, auto()
    DANG1_MUTED = "DANG1_MUTED", Note.DANG, 1, MutingType.MUTED, auto()
    DAING1_MUTED = "DAING1_MUTED", Note.DAING, 1, MutingType.MUTED, auto()
    DING2_MUTED = "DING2_MUTED", Note.DING, 2, MutingType.MUTED, auto()
    DONG2_MUTED = "DONG2_MUTED", Note.DONG, 2, MutingType.MUTED, auto()
    DENG2_MUTED = "DENG2_MUTED", Note.DENG, 2, MutingType.MUTED, auto()
    DEUNG2_MUTED = "DEUNG2_MUTED", Note.DEUNG, 2, MutingType.MUTED, auto()
    DUNG2_MUTED = "DUNG2_MUTED", Note.DUNG, 2, MutingType.MUTED, auto()
    DANG2_MUTED = "DANG2_MUTED", Note.DANG, 2, MutingType.MUTED, auto()
    DAING2_MUTED = "DAING2_MUTED", Note.DAING, 2, MutingType.MUTED, auto()
    GIR = "GIR", Note.GIR, None, MutingType.OPEN, auto()
    PUR = "PUR", Note.PUR, None, MutingType.OPEN, auto()
    TONG = "TONG", Note.TONG, None, MutingType.OPEN, auto()
    KEP = "KEP", Note.KEP, None, MutingType.OPEN, auto()
    PAK = "PAK", Note.PAK, None, MutingType.OPEN, auto()
    DUT = "DUT", Note.DUT, None, MutingType.OPEN, auto()
    TUT = "TUT", Note.TUT, None, MutingType.OPEN, auto()
    KRUM = "KRUM", Note.KRUM, None, MutingType.OPEN, auto()
    PUNG = "PUNG", Note.PUNG, None, MutingType.OPEN, auto()
    BYONG = "BYONG", Note.BYONG, None, MutingType.OPEN, auto()
    BYOT = "BYOT", Note.BYOT, None, MutingType.OPEN, auto()
    JET = "JET", Note.JET, None, MutingType.OPEN, auto()
    TICK = "TICK", Note.TICK, None, MutingType.OPEN, auto()
    TICK_1_PANGGUL = "TICK_1_PANGGUL", Note.TICK, None, MutingType.OPEN, auto()
    TICK_2_PANGGUL = "TICK_2_PANGGUL", Note.TICK, None, MutingType.OPEN, auto()
    KAP = "KAP", Note.KAP, None, MutingType.OPEN, auto()
    PEK = "PEK", Note.PEK, None, MutingType.OPEN, auto()
    DAG = "DAG", Note.DAG, None, MutingType.OPEN, auto()
    DUG = "DUG", Note.DUG, None, MutingType.OPEN, auto()
    TAK = "TAK", Note.TAK, None, MutingType.OPEN, auto()
    TEK = "TEK", Note.TEK, None, MutingType.OPEN, auto()
    PLAK = "PLAK", Note.PLAK, None, MutingType.OPEN, auto()
    MUTED = "MUTED", Note.MUTED, None, MutingType.OPEN, auto()
    OPEN = "OPEN", Note.OPEN, None, MutingType.OPEN, auto()
    MODIFIER_PREV1 = "MODIFIER_PREV1", None, None, MutingType.OPEN, auto()
    MODIFIER_PREV2 = "MODIFIER_PREV2", None, None, MutingType.OPEN, auto()
    SILENCE = "SILENCE", None, None, MutingType.OPEN, auto()
    EXTENSION = "EXTENSION", None, None, MutingType.OPEN, auto()
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED", None, None, MutingType.OPEN, auto()

    def __init__(self, symbolname, note, octave, mutingtype, sequence):
        self._value_ = symbolname
        self.note = note
        self.octave = octave
        self.mutingtype = mutingtype
        self.sequence = sequence

    def __repr__(self):
        return self.value

    def __str__(self):
        return self.value

    @property
    def is_nonnote(self):
        return not self.note

    @property
    def isnote(self):
        return self.note is not None

    @property
    def isrest(self):
        return self in [self.SILENCE, self.EXTENSION]


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

# if __name__ == "__main__":
#     for val in SymbolValue:
#         print(f"{val} - {val.note}{val.octave if val.octave is not None else ""}")


if __name__ == "__main__":
    for val in SymbolValue:
        print(val, val.seq)
