import codecs

from pianoroll import BALIMUSIC4_TO_MIDI

INSTRUMENT = str
BPM = int
PASS = int
DEFAULT = -1

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


# ==============================
NOTENAME = {
    0: ("dot", "silence (muted note)"),
    1: ("dash", "open note continuation"),
    35: ("dotless i underdot", "ding0"),
    36: ("o underdot", "dong0"),
    37: ("e underdot", "deng0"),
    38: ("u underdot", "dung0"),
    39: ("a underdot", "dang0"),
    40: ("dotless i", "ding1"),
    41: ("o", "dong1"),
    42: ("e", "deng1"),
    43: ("u", "dung1"),
    44: ("a", "dang1"),
    45: ("i (with dot)", "ding2"),
    46: ("o overdot", "dong2"),
    47: ("e overdot", "deng2"),
    48: ("u overdot", "dung2"),
    49: ("a overdot", "dang2"),
    60: ("G", "gir"),
    61: ("W", "gir wadon"),
    62: ("L", "gir lanang"),
    63: ("P", "pur"),
    64: ("T", "tong"),
    70: ("k", "ke"),
    71: ("p", "pak"),
    72: ("d", "dut"),
    73: ("t", "dut"),
    74: ("n", "krum"),
    75: ("u", "pung"),
    80: ("b", "byong"),
    81: ("x", "tick"),
}


NOTEDURATION = {
    (1, 0): ("", " open"),
    (0.25, 0.75): (" dashed", " long muted"),
    (0.125, 0.875): (" slashed", " muted"),
    (0.5, 0): (" single macron", " half duration"),
    (0.1, 0.4): (" slashed, single macron", " half duration long muted"),
    (0.25, 0): (" double macron", " quarter duration"),
    (0.05, 0.2): (" slashed, double macron", " quarter duration muted "),
}

if __name__ == "__main__":
    for key, note in BALIMUSIC4_TO_MIDI.items():
        # print(f"{note.symbol} - {note.description} - {note.balifont_symbol_description}")
        print(f"{note.symbol}  - {note.description} - {codecs.encode(note.symbol, encoding='unicode-escape')}")
