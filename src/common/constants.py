from enum import Enum, StrEnum, auto
from typing import Any

BPM = int
PASS = int
DEFAULT = -1
Duration = int
BeatId = str
Pass = int
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


# TODO should we create enums dynamically from settings files?
# See https://stackoverflow.com/questions/47299036/how-can-i-construct-an-enum-enum-from-a-dictionary-of-values
# Advantage: enum always in sync with data.
# Disadvantage: no autocomplete for values.


class NotationFont(NotationEnum):
    BALIMUSIC4 = "BaliMusic4"
    BALIMUSIC5 = "BaliMusic5"


class NoteSource(NotationEnum):
    # indicates whether the character occurs in the score
    # or was added by this application.
    # SCORE is also applicable for Pitch Characters that have been
    # changed by applying one or more Modifier Characters.
    SCORE = "SCORE"
    VALIDATOR = "VALIDATOR"


class InstrumentGroup(NotationEnum):
    # TODO replace with settings file
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
    # TODO replace with settings file
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


class Pitch(NotationEnum):
    # TODO replace with settings file
    # Note: Pitch.NONE and Pitch.TICK are used explicitly in code.
    DING = "DING"
    DONG = "DONG"
    DENG = "DENG"
    DEUNG = "DEUNG"
    DUNG = "DUNG"
    DANG = "DANG"
    DAING = "DAING"
    DENGDING = "DENGDING"
    BYONG = "BYONG"
    BYOT = "BYOT"
    KA = "KA"
    PAK = "PAK"
    DE = "DE"
    TUT = "TUT"
    JU = "JU"
    KUNG = "KUNG"
    PLAK = "PLAK"
    DAG = "DAG"
    DUG = "DUG"
    GIR = "GIR"
    JET = "JET"
    MUTED = "MUTED"
    OPEN = "OPEN"
    PEK = "PEK"
    PUR = "PUR"
    TICK = "TICK"
    TICK_2_PANGGUL = "TICK_2_PANGGUL"
    TONG = "TONG"
    NONE = "NONE"


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


if __name__ == "__main__":
    print(InstrumentType.CALUNG.sequence)
