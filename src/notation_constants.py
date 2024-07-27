from enum import StrEnum

BPM = int
PASS = int
DEFAULT = -1


class InstrumentGroup(StrEnum):
    GONG_KEBYAR = "GONG_KEBYAR"
    SEMAR_PAGULINGAN = "SEMAR_PAGULINGAN"


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


class SymbolValue(StrEnum):
    # 0=lower instrument octave, 1=central instrument octave, 2=higher instrument octave.
    # The octave numbering is relative to the instrument's range.
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
    DING0_MUTED = "DING0_MUTED"
    DONG0_MUTED = "DONG0_MUTED"
    DENG0_MUTED = "DENG0_MUTED"
    DEUNG0_MUTED = "DEUNG0_MUTED"
    DUNG0_MUTED = "DUNG0_MUTED"
    DANG0_MUTED = "DANG0_MUTED"
    DAING0_MUTED = "DAING0_MUTED"
    DING1_MUTED = "DING1_MUTED"
    DONG1_MUTED = "DONG1_MUTED"
    DENG1_MUTED = "DENG1_MUTED"
    DEUNG1_MUTED = "DEUNG1_MUTED"
    DUNG1_MUTED = "DUNG1_MUTED"
    DANG1_MUTED = "DANG1_MUTED"
    DAING1_MUTED = "DAING1_MUTED"
    DING2_MUTED = "DING2_MUTED"
    DONG2_MUTED = "DONG2_MUTED"
    DENG2_MUTED = "DENG2_MUTED"
    DEUNG2_MUTED = "DEUNG2_MUTED"
    DUNG2_MUTED = "DUNG2_MUTED"
    DANG2_MUTED = "DANG2_MUTED"
    DAING2_MUTED = "DAING2_MUTED"
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

if __name__ == "__main__":
    for val in InstrumentPosition:
        x = InstrumentPosition.CALUNG
        print(f"{val} - {val.instrumenttype}")
