from enum import Enum, StrEnum, auto

BPM = int
PASS = int
ALL_PASSES = -1
Duration = int
BeatId = str


class NotationEnum(StrEnum):
    def __repr__(self):
        # Enables to parse string values correctly
        return self.value

    def __str__(self):
        return self.name

    @classmethod
    def from_value(cls, value):
        enum = next((el for el in cls if value in [el.name, el.value]), None)
        return enum

    @property
    def sequence(self):
        return list(self.__class__).index(self)


class NotationFont(NotationEnum):
    BALIMUSIC4 = "Bali Music 4"
    BALIMUSIC5 = "Bali Music 5"


class MidiVersion(NotationEnum):
    """Lists the possible midi mappings to choose from in the midinotes.tsv settings file.
    This settings file maps instrument/note combinations to a midi pianoroll key value.
    """

    SINGLE_INSTR = "midi-gk1"
    MULTIPLE_INSTR = "midi-gk2"
    PIANO = "midi-piano"

    @classmethod
    def from_value(cls, value):
        enum = next((el for el in cls if el.value == value), None)
        if not enum:
            raise ValueError(
                f"Value {value} not in {cls.__name__} enum class. If you added a column with this name "
                "to the midi settings file, please add the new column name to the MidiValue enum class."
            )
        return enum


class InstrumentGroup(NotationEnum):
    GONG_KEBYAR = "GONG_KEBYAR"
    SEMAR_PAGULINGAN = "SEMAR_PAGULINGAN"
    GONG_PELEGONGAN = "GONG_PELEGONGAN"
    GENDER_WAYANG = "GENDER_WAYANG"


class InstrumentType(NotationEnum):
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


class InstrumentPosition(NotationEnum):
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

    @property
    def instrumenttype(self):
        return InstrumentType[self.split("_")[0]]


class NoteType(NotationEnum):
    MELODIC = "MELODIC"
    PERCUSSION = "PERCUSSION"


class MutingType(NotationEnum):
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
    DENGDING = "DENGDING", NoteType.MELODIC, auto()
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
    DING0 = "DING0", Note.DING, 0, MutingType.OPEN
    DONG0 = "DONG0", Note.DONG, 0, MutingType.OPEN
    DENG0 = "DENG0", Note.DENG, 0, MutingType.OPEN
    DEUNG0 = "DEUNG0", Note.DEUNG, 0, MutingType.OPEN
    DUNG0 = "DUNG0", Note.DUNG, 0, MutingType.OPEN
    DANG0 = "DANG0", Note.DANG, 0, MutingType.OPEN
    DAING0 = "DAING0", Note.DAING, 0, MutingType.OPEN
    DING1 = "DING1", Note.DING, 1, MutingType.OPEN
    DONG1 = "DONG1", Note.DONG, 1, MutingType.OPEN
    DENG1 = "DENG1", Note.DENG, 1, MutingType.OPEN
    DEUNG1 = "DEUNG1", Note.DEUNG, 1, MutingType.OPEN
    DUNG1 = "DUNG1", Note.DUNG, 1, MutingType.OPEN
    DANG1 = "DANG1", Note.DANG, 1, MutingType.OPEN
    DAING1 = "DAING1", Note.DAING, 1, MutingType.OPEN
    DING2 = "DING2", Note.DING, 2, MutingType.OPEN
    DONG2 = "DONG2", Note.DONG, 2, MutingType.OPEN
    DENG2 = "DENG2", Note.DENG, 2, MutingType.OPEN
    DEUNG2 = "DEUNG2", Note.DEUNG, 2, MutingType.OPEN
    DUNG2 = "DUNG2", Note.DUNG, 2, MutingType.OPEN
    DANG2 = "DANG2", Note.DANG, 2, MutingType.OPEN
    DAING2 = "DAING2", Note.DAING, 2, MutingType.OPEN
    DENGDING0 = "DENGDING0", Note.DENGDING, 0, MutingType.OPEN
    DING0_MUTED = "DING0_MUTED", Note.DING, 0, MutingType.MUTED
    DONG0_MUTED = "DONG0_MUTED", Note.DONG, 0, MutingType.MUTED
    DENG0_MUTED = "DENG0_MUTED", Note.DENG, 0, MutingType.MUTED
    DEUNG0_MUTED = "DEUNG0_MUTED", Note.DEUNG, 0, MutingType.MUTED
    DUNG0_MUTED = "DUNG0_MUTED", Note.DUNG, 0, MutingType.MUTED
    DANG0_MUTED = "DANG0_MUTED", Note.DANG, 0, MutingType.MUTED
    DAING0_MUTED = "DAING0_MUTED", Note.DAING, 0, MutingType.MUTED
    DING1_MUTED = "DING1_MUTED", Note.DING, 1, MutingType.MUTED
    DONG1_MUTED = "DONG1_MUTED", Note.DONG, 1, MutingType.MUTED
    DENG1_MUTED = "DENG1_MUTED", Note.DENG, 1, MutingType.MUTED
    DEUNG1_MUTED = "DEUNG1_MUTED", Note.DEUNG, 1, MutingType.MUTED
    DUNG1_MUTED = "DUNG1_MUTED", Note.DUNG, 1, MutingType.MUTED
    DANG1_MUTED = "DANG1_MUTED", Note.DANG, 1, MutingType.MUTED
    DAING1_MUTED = "DAING1_MUTED", Note.DAING, 1, MutingType.MUTED
    DING2_MUTED = "DING2_MUTED", Note.DING, 2, MutingType.MUTED
    DONG2_MUTED = "DONG2_MUTED", Note.DONG, 2, MutingType.MUTED
    DENG2_MUTED = "DENG2_MUTED", Note.DENG, 2, MutingType.MUTED
    DEUNG2_MUTED = "DEUNG2_MUTED", Note.DEUNG, 2, MutingType.MUTED
    DUNG2_MUTED = "DUNG2_MUTED", Note.DUNG, 2, MutingType.MUTED
    DANG2_MUTED = "DANG2_MUTED", Note.DANG, 2, MutingType.MUTED
    DAING2_MUTED = "DAING2_MUTED", Note.DAING, 2, MutingType.MUTED
    GIR = "GIR", Note.GIR, None, MutingType.OPEN
    PUR = "PUR", Note.PUR, None, MutingType.OPEN
    TONG = "TONG", Note.TONG, None, MutingType.OPEN
    KEP = "KEP", Note.KEP, None, MutingType.OPEN
    PAK = "PAK", Note.PAK, None, MutingType.OPEN
    DUT = "DUT", Note.DUT, None, MutingType.OPEN
    TUT = "TUT", Note.TUT, None, MutingType.OPEN
    KRUM = "KRUM", Note.KRUM, None, MutingType.OPEN
    PUNG = "PUNG", Note.PUNG, None, MutingType.OPEN
    BYONG = "BYONG", Note.BYONG, None, MutingType.OPEN
    BYOT = "BYOT", Note.BYOT, None, MutingType.OPEN
    JET = "JET", Note.JET, None, MutingType.OPEN
    TICK_1_PANGGUL = "TICK_1_PANGGUL", Note.TICK, None, MutingType.OPEN
    TICK_2_PANGGUL = "TICK_2_PANGGUL", Note.TICK, None, MutingType.OPEN
    OPEN = "OPEN", Note.OPEN, None, MutingType.OPEN
    MUTED = "MUTED", Note.MUTED, None, MutingType.MUTED
    KAP = "KAP", Note.KAP, None, MutingType.OPEN
    PEK = "PEK", Note.PEK, None, MutingType.OPEN
    DAG = "DAG", Note.DAG, None, MutingType.OPEN
    DUG = "DUG", Note.DUG, None, MutingType.OPEN
    TAK = "TAK", Note.TAK, None, MutingType.OPEN
    TEK = "TEK", Note.TEK, None, MutingType.OPEN
    PLAK = "PLAK", Note.PLAK, None, MutingType.OPEN
    SILENCE = "SILENCE", None, None, None
    EXTENSION = "EXTENSION", None, None, None
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED", None, None, None
    # Bali Music 4 font
    MODIFIER_PREV1 = "MODIFIER_PREV1", None, None, None
    MODIFIER_PREV2 = "MODIFIER_PREV2", None, None, None
    # Bali Music 5 font
    GRACE_DING = "GRACE_DING", Note.DING, 1, MutingType.OPEN
    GRACE_DONG = "GRACE_DONG", Note.DONG, 1, MutingType.OPEN
    GRACE_DENG = "GRACE_DENG", Note.DENG, 1, MutingType.OPEN
    GRACE_DUNG = "GRACE_DUNG", Note.DUNG, 1, MutingType.OPEN
    GRACE_DANG = "GRACE_DANG", Note.DANG, 1, MutingType.OPEN
    MOD_MUTE = "MUTE", None, None, MutingType.OPEN
    MOD_ABBREVIATE = "MOD_ABBREVIATE", None, None, MutingType.OPEN
    MOD_QUARTER_NOTE = "MOD_QUARTER_NOTE", None, None, MutingType.OPEN
    MOD_HALF_NOTE = "MOD_HALF_NOTE", None, None, MutingType.OPEN
    MOD_OCTAVE_0 = "MOD_OCTAVE_0", None, None, MutingType.OPEN
    MOD_OCTAVE_2 = "MOD_OCTAVE_2", None, None, MutingType.OPEN

    def __init__(self, symbolname, note, octave, mutingtype):
        self._value_ = symbolname
        self.note = note
        self.octave = octave
        self.mutingtype = mutingtype

        # self.sequence = sequence

    def __repr__(self):
        return self.value

    def __str__(self):
        return self.value

    @property
    def sequence(self):
        return list(self.__class__).index(self)

    @property
    def is_nonnote(self):
        return not self.note

    @property
    def isnote(self):
        return self.note is not None

    @property
    def isrest(self):
        return self in [self.SILENCE, self.EXTENSION]


class GonganType(NotationEnum):
    KEBYAR = "kebyar"
    REGULAR = "regular"


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


# if __name__ == "__main__":
#     for val in SymbolValue:
#         print(f"{val} - {val.note}{val.octave if val.octave is not None else ""}")


if __name__ == "__main__":
    print(InstrumentType.CALUNG.sequence)
