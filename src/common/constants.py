from enum import Enum, StrEnum, auto

BPM = int
PASS = int
ALL_PASSES = -1
Duration = int
BeatId = str
Octave = int
MIDIvalue = int


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


class CharacterSource(NotationEnum):
    # indicates whether the character occurs in the score
    # or was added by this application.
    # SCORE is also applicable for Note Characters that have been
    # changed by applying one or more Modifier Characters.
    SCORE = "SCORE"
    VALIDATOR = "VALIDATOR"


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
    NONE = "NONE"


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
    TICK_2_PANGGUL = "TICK_2_PANGGUL", NoteType.PERCUSSION, auto()
    TONG = "TONG", NoteType.PERCUSSION, auto()
    TUT = "TUT", NoteType.PERCUSSION, auto()
    NONE = "NONE", NoteType.NONE, auto()

    def __init__(self, notename: str, notetype: NoteType, sequence: int):
        self._value_ = notename
        self.type = notetype
        self.sequence = sequence

    def __repr__(self):
        return self.value

    def __str__(self):
        return self.value


class Stroke(NotationEnum):
    OPEN = "OPEN"
    MUTED = "MUTED"
    ABBREVIATED = "ABBREVIATED"
    EXTENSION = "EXTENSION"
    SILENCE = "SILENCE"
    NONE = "NONE"


class Modifier(StrEnum):
    NONE = "NONE"
    # Font4
    MODIFIER_PREV1 = "MODIFIER_PREV1"
    MODIFIER_PREV2 = "MODIFIER_PREV2"
    # Font5
    GRACE_NOTE = "GRACE_NOTE"
    OCTAVE_0 = "OCTAVE_0"
    OCTAVE_2 = "OCTAVE_2"
    MUTE = "MUTE"
    ABBREVIATE = "ABBREVIATE"
    HALF_NOTE = "HALF_NOTE"
    QUARTER_NOTE = "QUARTER_NOTE"
    TREMOLO = "TREMOLO"
    TREMOLO_ACCELERATING = "TREMOLO_ACCELERATING"
    NOROT = "NOROT"


# MetaData related constants
class MetaDataStatus(NotationEnum):
    OFF = "off"
    ON = "on"


class GonganType(NotationEnum):
    REGULAR = "regular"
    KEBYAR = "kebyar"
    GINEMAN = "gineman"


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
