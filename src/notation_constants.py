from enum import IntEnum, StrEnum, auto

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
    GONGS = "GONGS"
    KEMPLI = "KEMPLI"
    CENGCENG = "CENGCENG"
    KENDANG = "KENDANG"
    JEGOGAN = "JEGOGAN"
    CALUNG = "CALUNG"
    PENYACAH = "PENYACAH"
    PEMADE_POLOS = "PEMADE_POLOS"
    PEMADE_SANGSIH = "PEMADE_SANGSIH"
    KANTILAN_POLOS = "KANTILAN_POLOS"
    KANTILAN_SANGSIH = "KANTILAN_SANGSIH"
    UGAL = "UGAL"
    GENDERRAMBAT = "GENDERRAMBAT"
    GENDERWAYANG_POLOS = "GENDERWAYANG_POLOS"
    GENDERWAYANG_SANGSIH = "GENDERWAYANG_SANGSIH"
    REYONG_1 = "REYONG_1"
    REYONG_2 = "REYONG_2"
    REYONG_3 = "REYONG_3"
    REYONG_4 = "REYONG_4"
    TROMPONG = "TROMPONG"

    def __repr__(self):
        # Enables to decode list of values
        return self.value

    @property
    def instrumenttype(self):
        return InstrumentType[self.split("_")[0]]


class Note(StrEnum):
    DING = "DING"
    DONG = "DONG"
    DENG = "DENG"
    DEUNG = "DEUNG"
    DUNG = "DUNG"
    DANG = "DANG"
    DAING = "DAING"
    BYONG = "BYONG"
    BYOT = "BYOT"
    DAG = "DAG"
    DUG = "DUG"
    DUT = "DUT"
    GIR = "GIR"
    JET = "JET"
    KAP = "KAP"
    KEP = "KEP"
    KRUM = "KRUM"
    MUTED = "MUTED"
    OPEN = "OPEN"
    PAK = "PAK"
    PEK = "PEK"
    PLAK = "PLAK"
    PUNG = "PUNG"
    PUR = "PUR"
    TAK = "TAK"
    TEK = "TEK"
    TICK = "TICK"
    TONG = "TONG"
    TUT = "TUT"

    # TODO: better to make this explicit per instrument
    def kempyung(self, octave: int, instrumentgroup: InstrumentGroup):
        if instrumentgroup == InstrumentGroup.GONG_KEBYAR:
            pairs = {
                (self.DONG, 0): (self.DANG, 0),
                (self.DENG, 0): (self.DING, 1),
                (self.DUNG, 0): (self.DONG, 1),
                (self.DANG, 0): (self.DENG, 1),
                (self.DING, 1): (self.DUNG, 1),
                (self.DONG, 1): (self.DANG, 1),
                (self.DENG, 1): (self.DING, 2),
                (self.DUNG, 1): (self.DUNG, 1),
                (self.DANG, 1): (self.DANG, 1),
                (self.DING, 2): (self.DANG, 2),
            }
            return pairs.get((self, octave), None)
        return None


class SymbolValue(StrEnum):
    # 0=lower instrument octave, 1=central instrument octave, 2=higher instrument octave.
    # The octave numbering is relative to the instrument's range.
    DING_0 = "DING_0"
    DONG_0 = "DONG_0"
    DENG_0 = "DENG_0"
    DEUNG_0 = "DEUNG_0"
    DUNG_0 = "DUNG_0"
    DANG_0 = "DANG_0"
    DAING_0 = "DAING_0"
    DING_1 = "DING_1"
    DONG_1 = "DONG_1"
    DENG_1 = "DENG_1"
    DEUNG_1 = "DEUNG_1"
    DUNG_1 = "DUNG_1"
    DANG_1 = "DANG_1"
    DAING_1 = "DAING_1"
    DING_2 = "DING_2"
    DONG_2 = "DONG_2"
    DENG_2 = "DENG_2"
    DEUNG_2 = "DEUNG_2"
    DUNG_2 = "DUNG_2"
    DANG_2 = "DANG_2"
    DAING_2 = "DAING_2"
    DING_0_MUTED = "DING_0_MUTED"
    DONG_0_MUTED = "DONG_0_MUTED"
    DENG_0_MUTED = "DENG_0_MUTED"
    DEUNG_0_MUTED = "DEUNG_0_MUTED"
    DUNG_0_MUTED = "DUNG_0_MUTED"
    DANG_0_MUTED = "DANG_0_MUTED"
    DAING_0_MUTED = "DAING_0_MUTED"
    DING_1_MUTED = "DING_1_MUTED"
    DONG_1_MUTED = "DONG_1_MUTED"
    DENG_1_MUTED = "DENG_1_MUTED"
    DEUNG_1_MUTED = "DEUNG_1_MUTED"
    DUNG_1_MUTED = "DUNG_1_MUTED"
    DANG_1_MUTED = "DANG_1_MUTED"
    DAING_1_MUTED = "DAING_1_MUTED"
    DING_2_MUTED = "DING_2_MUTED"
    DONG_2_MUTED = "DONG_2_MUTED"
    DENG_2_MUTED = "DENG_2_MUTED"
    DEUNG_2_MUTED = "DEUNG_2_MUTED"
    DUNG_2_MUTED = "DUNG_2_MUTED"
    DANG_2_MUTED = "DANG_2_MUTED"
    DAING_2_MUTED = "DAING_2_MUTED"
    GIR = "GIR"
    PUR = "PUR"
    TONG = "TONG"
    KEP = "KEP"
    PAK = "PAK"
    DUT = "DUT"
    TUT = "TUT"
    KRUM = "KRUM"
    PUNG = "PUNG"
    BYONG = "BYONG"
    BYOT = "BYOT"
    JET = "JET"
    TICK = "TICK"
    TICK_1_PANGGUL = "TICK_1_PANGGUL"
    TICK_2_PANGGUL = "TICK_2_PANGGUL"
    KAP = "KAP"
    PEK = "PEK"
    DAG = "DAG"
    DUG = "DUG"
    TAK = "TAK"
    TEK = "TEK"
    PLAK = "PLAK"
    MUTED = "MUTED"
    OPEN = "OPEN"
    MODIFIER_PREV1 = "MODIFIER_PREV1"
    MODIFIER_PREV2 = "MODIFIER_PREV2"
    SILENCE = "SILENCE"
    EXTENSION = "EXTENSION"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"

    @property
    def note(self):
        # TODO: safer to make this property explicit
        basicvalue = self.value.split("_")[0]
        return Note[basicvalue] if basicvalue in Note else None

    @property
    def octave(self):
        # TODO: safer to make this property explicit
        parts = self.value.split("_")
        if not len(parts) > 1 and not (parts[0].startswith("D") and parts[0].endswith("NG")):
            return None
        else:
            return int(parts[1])

    @property
    def is_nonnote(self):
        non_notes = [
            self.MODIFIER_PREV1,
            self.MODIFIER_PREV2,
            self.SILENCE,
            self.EXTENSION,
            self.NOT_IMPLEMENTED,
        ]
        return self in non_notes

    @property
    def isnote(self):
        return self.note is not None

    @property
    def isrest(self):
        return self in [self.SILENCE, self.EXTENSION]

    # TODO: better to make this explicit per instrument
    def iskempyungof(self, other: "SymbolValue", instrumentgroup: InstrumentGroup) -> bool:
        if self.octave and other.octave:
            return other.note.kempyung(other.octave, instrumentgroup) == (self.note, self.octave)
        return False


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

if __name__ == "__main__":
    for val in SymbolValue:
        if not val.note:
            print(f"{val} - {val.note}")
