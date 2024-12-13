from enum import StrEnum
from typing import Any

from src.common.logger import get_logger

logger = get_logger(__name__)

BPM = int
Velocity = int
PASS = int
DEFAULT = -1
Duration = int
BeatId = str
Pass = int
Octave = int
MIDIvalue = int
MidiDict = dict[str, list[dict[str, str | int | None]]]
NotationDict = dict[int, dict[int, dict[str, dict[tuple[int], str]]]]  # notation[gongan_id][beat_id][position][passes]
NoteRecord = dict[str, Any]
ErrorMessage = str


class SpecialTags(StrEnum):
    # Putting constants in a class enables them to be used in a `match`statement
    # See e.g. https://github.com/microsoft/pylance-release/issues/4309
    METADATA = "metadata"
    COMMENT = "comment"


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
    REYONG = "REYONG"
    GENDERRAMBAT = "GENDERRAMBAT"
    TROMPONG = "TROMPONG"
    GENDERWAYANG = "GENDERWAYANG"
    SULING = "SULING"


class Position(NotationEnum):
    # TODO replace with settings file
    # The sorting order affects the layout of the
    # corrected score (see common.utils.gongan_to_records)
    UGAL = "UGAL"
    SULING = "SULING"
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
    PENYACAH = "PENYACAH"
    CALUNG = "CALUNG"
    JEGOGAN = "JEGOGAN"
    KENDANG = "KENDANG"
    CENGCENG = "CENGCENG"
    GONGS = "GONGS"
    KEMPLI = "KEMPLI"
    GENDERWAYANG_POLOS = "GENDERWAYANG_POLOS"
    GENDERWAYANG_SANGSIH = "GENDERWAYANG_SANGSIH"

    @property
    def instrumenttype(self):
        return InstrumentType[self.split("_")[0]]

    @property
    def shortcode(self):
        return self.value.replace("_POLOS", "_P").replace("_SANGSIH", "_S").replace("WAYANG", "").replace("RAMBAT", "")


class Pitch(NotationEnum):
    # TODO replace with settings file
    # Note: Pitch.NONE and Pitch.STRIKE are used explicitly in code.
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
    CUNG = "CUNG"
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
    STRIKE = "STRIKE"
    TONG = "TONG"
    NONE = "NONE"


class Stroke(NotationEnum):
    OPEN = "OPEN"
    MUTED = "MUTED"
    ABBREVIATED = "ABBREVIATED"
    TICK1 = "TICK1"
    TICK2 = "TICK2"
    KAPAK = "KAPAK"
    DETUT = "DETUT"
    CUNGKUNG = "CUNGKUNG"
    TREMOLO = "TREMOLO"
    TREMOLO_ACCELERATING = "TREMOLO_ACCELERATING"
    EXTENSION = "EXTENSION"
    SILENCE = "SILENCE"
    NOROT = "NOROT"
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


class AnimationProfiles(NotationEnum):
    GK_GONGS = "GK_GONGS"
    GK_KENDANG = "GK_KENDANG"
    GK_POKOK = "GK_POKOK"
    GK_GANGSA = "GK_GANGSA"
    GK_REYONG = "GK_REYONG"
    SP_GONGS = "SP_GONGS"
    SP_KENDANG = "SP_KENDANG"
    SP_POKOK = "SP_POKOK"
    SP_GANGSA = "SP_GANGSA"
    SP_TROMPONG = "SP_TROMPONG"


class NoteOct(NotationEnum):
    DING0 = "DING0"
    DONG0 = "DONG0"
    DENG0 = "DENG0"
    DEUNG0 = "DEUNG0"
    DUNG0 = "DUNG0"
    DANG0 = "DANG0"
    DAING0 = "DAING0"
    DING1 = "DING1"
    DONG1 = "DONG1"
    DENG1 = "DENG1"
    DEUNG1 = "DEUNG1"
    DUNG1 = "DUNG1"
    DANG1 = "DANG1"
    DAING1 = "DAING1"
    DING2 = "DING2"
    DONG2 = "DONG2"
    DENG2 = "DENG2"
    DEUNG2 = "DEUNG2"
    DUNG2 = "DUNG2"
    DANG2 = "DANG2"
    DAING2 = "DAING2"
    DENGDING = "DENGDING"
    BYONG = "BYONG"
    BYOT = "BYOT"
    KA = "KA"
    PAK = "PAK"
    DE = "DE"
    TUT = "TUT"
    CUNG = "CUNG"
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
    STRIKE = "STRIKE"
    TONG = "TONG"


class DynamicLevel(NotationEnum):
    PIANISSIMO = "pp"
    PIANO = "p"
    MEZZOPIANO = "mp"
    MEZZOFORTE = "mf"
    FORTE = "f"
    FORTISSIMO = "ff"


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
    logger.info(InstrumentType.CALUNG.sequence)
