import codecs
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

Instrument = str
BPM = int
Pass = int
DEFAULT = -1

# MIDI to Notation


@dataclass
class TimedMessage:
    time: int
    type: str
    note: str = "."
    cumtime: int = -1
    duration: int = -1


@dataclass
class TimingData:
    unit_duration: int
    units_per_beat: int
    beats_per_gongan: int


# Notation to MIDI


@dataclass
class Note:
    note: int
    duration: float
    rest_after: float
    description: str
    symbol: str
    unicodes: str = ""
    unicode: int = 0
    symbol_description: str = ""
    balifont_symbol_description: str = ""


# Metadata
class Tempo(BaseModel):
    type: Literal["tempo"]
    bpm: int
    passes: list[Pass] = field(default_factory=list)
    first_beat: Optional[int] = 1
    beats: Optional[int] = 0
    passes: Optional[list[int]] = field(default_factory=list)  # On which pass(es) should goto be performed?

    @computed_field
    @property
    def first_beat_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.first_beat - 1

    @model_validator(mode="after")
    def set_default_pass(self):
        if not self.passes:
            self.passes.append(DEFAULT)
        return self


class Label(BaseModel):
    type: Literal["label"]
    label: str
    beat_nr: Optional[int] = 1

    @computed_field
    @property
    def beat_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.beat_nr - 1


class GoTo(BaseModel):
    type: Literal["goto"]
    label: str
    beat_nr: Optional[int] | None = None  # Beat number from which to goto. Default is last beat of the system.
    passes: Optional[list[int]] = field(default_factory=list)  # On which pass(es) should goto be performed?

    @computed_field
    @property
    def beat_seq(self) -> int:
        # Returns the pythonic sequence id (numbered from 0)
        return self.beat_nr - 1 if self.beat_nr else -1


class MetaData(BaseModel):
    data: Union[Tempo, Label, GoTo] = Field(..., discriminator="type")


# Flow


@dataclass
class Beat:
    id: int
    bpm: dict[int, BPM]
    # bpm_alt: dict[Pass, BPM]  # TODO Not implemented yet. First need to find out how to combine with next_bpm
    next_bpm: dict[int, BPM]
    duration: float
    notes: dict[Instrument, list[Note]] = field(default_factory=dict)
    next: "Beat" = field(default=None, repr=False)
    goto: dict[Pass, "Beat"] = field(default_factory=dict)
    _pass_: int = 0  # Counts the number of times the beat is passed during generation of MIDI file.

    def get_bpm(self):
        return self.bpm.get(self._pass_, self.bpm.get(DEFAULT, None))

    def get_next_bpm(self):
        return self.next_bpm.get(self._pass_, self.next_bpm.get(DEFAULT, None))


@dataclass
class System:
    # A set of beats.
    # A System will usually span one gongan.
    id: int
    beats: list[Beat] = field(default_factory=list)


@dataclass
class Score:
    title: str
    systems: list[System] = field(default_factory=list)


@dataclass
class FlowInfo:
    labels: dict[str, Beat] = field(default_factory=dict)
    gotos: dict[str, tuple[System, GoTo]] = field(default_factory=lambda: defaultdict(list))


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

# special note values: -1 = modifies previous note, 0 = rest, 1 = extends previous.
# key ranges: 0=lower range, 1=mid range, 2=higher range (these denote different frequency ranges per instrument)
# stroke: open=unmuted, short=muted immediately after stroke, muted=muted during stroke
# fmt: off
BALIMUSIC4_TO_MIDI = {
    "'": Note(note=1, duration=0.5, rest_after=0, description='open note continuation half duration', symbol='´', unicode=0x00b4, symbol_description='acute', balifont_symbol_description='dash single macron'),
    '"': Note(note=1, duration=0.25, rest_after=0, description='open note continuation quarter duration', symbol='¨', unicode=0x00a8, symbol_description='trema', balifont_symbol_description='dash double macron'),
    "#": Note(note=47, duration=0.125, rest_after=0.875, description='deng2 muted', symbol='#', unicode=0x0023, symbol_description='sharp', balifont_symbol_description='e overdot slashed'),
    "&": Note(note=48, duration=0.125, rest_after=0.875, description='dung2 muted', symbol='&', unicode=0x0026, symbol_description='ampersand', balifont_symbol_description='u overdot slashed'),
    "(": Note(note=46, duration=0.125, rest_after=0.875, description='dong2 muted', symbol='(', unicode=0x0028, symbol_description='left round bracket', balifont_symbol_description='o overdot slashed'),
    "*": Note(note=45, duration=0.125, rest_after=0.875, description='ding2 muted', symbol='*', unicode=0x002a, symbol_description='', balifont_symbol_description='i (with dot) slashed'),
    "-": Note(note=1, duration=1, rest_after=0, description='open note continuation', symbol='-', unicode=0x002d, symbol_description='hyphen', balifont_symbol_description='dash'),
    ".": Note(note=0, duration=1, rest_after=0, description='silence (muted note) open', symbol='.', unicode=0x002e, symbol_description='period', balifont_symbol_description='dot'),
    "/": Note(note=-1, duration=0.25, rest_after=0.75, description='long mutes previous note', symbol='/', unicode=0x002f, symbol_description='', balifont_symbol_description='slash'),
    "3": Note(note=47, duration=1, rest_after=0, description='deng2 open', symbol='3', unicode=0x0033, symbol_description='digit 3', balifont_symbol_description='e overdot'),
    "7": Note(note=48, duration=1, rest_after=0, description='dung2 open', symbol='7', unicode=0x0037, symbol_description='digit 7', balifont_symbol_description='u overdot'),
    "8": Note(note=45, duration=1, rest_after=0, description='ding2 open', symbol='8', unicode=0x0038, symbol_description='digit 8', balifont_symbol_description='i (with dot)'),
    "9": Note(note=46, duration=1, rest_after=0, description='dong2 open', symbol='9', unicode=0x0039, symbol_description='digit 9', balifont_symbol_description='o overdot'),
    # "=": Note(note=999, duration=1, rest_after=0, description=' open', symbol='=', unicode=0x003d, symbol_description='equal', balifont_symbol_description=''),
    "A": Note(note=44, duration=0.125, rest_after=0.875, description='dang1 muted', symbol='A', unicode=0x0041, symbol_description='uppercase A', balifont_symbol_description='a slashed'),
    "B": Note(note=999, duration=0.125, rest_after=0.875, description='jet', symbol='B', unicode=0x0042, symbol_description='uppercase B', balifont_symbol_description='b slashed'),
    "D": Note(note=37, duration=0.125, rest_after=0.875, description='deng0 muted', symbol='D', unicode=0x0044, symbol_description='uppercase D', balifont_symbol_description='e underdot slashed'),
    "E": Note(note=42, duration=0.125, rest_after=0.875, description='deng1 muted', symbol='E', unicode=0x0045, symbol_description='uppercase E', balifont_symbol_description='e slashed'),
    "g": Note(note=60, duration=4, rest_after=0, description='gir', symbol='g', unicode=0x0067, symbol_description='lowercase g', balifont_symbol_description='G'),       
    "I": Note(note=40, duration=0.125, rest_after=0.875, description='ding1 muted', symbol='I', unicode=0x0049, symbol_description='uppercase I', balifont_symbol_description='dotless i slashed'),
    "J": Note(note=38, duration=0.125, rest_after=0.875, description='dung0 muted', symbol='J', unicode=0x004a, symbol_description='uppercase J', balifont_symbol_description='u underdot slashed'),
    "K": Note(note=35, duration=1, rest_after=0, description='ding0 open', symbol='K', unicode=0x004b, symbol_description='uppercase K', balifont_symbol_description='dotless i underdot'),
    "L": Note(note=36, duration=0.125, rest_after=0.875, description='dong0 muted', symbol='L', unicode=0x004c, symbol_description='uppercase L', balifont_symbol_description='o underdot slashed'),
    "O": Note(note=41, duration=0.125, rest_after=0.875, description='dong1 muted', symbol='O', unicode=0x004f, symbol_description='uppercase O', balifont_symbol_description='o slashed'),
    "P": Note(note=63, duration=4, rest_after=0, description='pur', symbol='P', unicode=0x0050, symbol_description='uppercase P', balifont_symbol_description='P'),        
    "Q": Note(note=49, duration=0.125, rest_after=0.875, description='dang2 muted', symbol='Q', unicode=0x0051, symbol_description='uppercase Q', balifont_symbol_description='a overdot slashed'),
    # "R": Note(note=999, duration=0.125, rest_after=0.875, description='deung muted', symbol='R', unicode=0x0052, symbol_description='uppercase R', balifont_symbol_description=' slashed'),
    # "S": Note(note=999, duration=0.125, rest_after=0.875, description='daing muted', symbol='S', unicode=0x0053, symbol_description='uppercase S', balifont_symbol_description=' slashed'),
    "T": Note(note=64, duration=4, rest_after=0, description='tong', symbol='T', unicode=0x0054, symbol_description='uppercase T', balifont_symbol_description='T'),       
    "U": Note(note=43, duration=0.125, rest_after=0.875, description='dung1 muted', symbol='U', unicode=0x0055, symbol_description='uppercase U', balifont_symbol_description='u slashed'),
    "W": Note(note=61, duration=4, rest_after=0, description='gir wadon', symbol='W', unicode=0x0057, symbol_description='uppercase W', balifont_symbol_description='W'),  
    "X": Note(note=81, duration=0.125, rest_after=0.875, description='tick muted', symbol='X', unicode=0x0058, symbol_description='uppercase X', balifont_symbol_description=' slashed'),
    "Y": Note(note=37, duration=1, rest_after=0, description='deng0 open', symbol='Y', unicode=0x0059, symbol_description='uppercase Y', balifont_symbol_description='e underdot'),
    "Z": Note(note=39, duration=0.125, rest_after=0.875, description='dang0 muted', symbol='Z', unicode=0x005a, symbol_description='uppercase Z', balifont_symbol_description='a underdot slashed'),
    # "_": Note(note=999, duration=1, rest_after=0, description=' open', symbol='_', unicode=0x005f, symbol_description='underscore', balifont_symbol_description=''),     
    "a": Note(note=44, duration=1, rest_after=0, description='dang1 open', symbol='a', unicode=0x0061, symbol_description='lowercase a', balifont_symbol_description='a'), 
    "b": Note(note=80, duration=1, rest_after=0, description='byong', symbol='b', unicode=0x0062, symbol_description='lowercase b', balifont_symbol_description='b'), 
    "d": Note(note=37, duration=1, rest_after=0, description='deng0 open', symbol='d', unicode=0x0064, symbol_description='lowercase d', balifont_symbol_description='e underdot'),
    "e": Note(note=42, duration=1, rest_after=0, description='deng1 open', symbol='e', unicode=0x0065, symbol_description='lowercase e', balifont_symbol_description='e'),
    "i": Note(note=40, duration=1, rest_after=0, description='ding1 open', symbol='i', unicode=0x0069, symbol_description='lowercase i', balifont_symbol_description='dotless i'),
    "j": Note(note=38, duration=1, rest_after=0, description='dung0 open', symbol='j', unicode=0x006a, symbol_description='lowercase j', balifont_symbol_description='u underdot'),
    "k": Note(note=35, duration=1, rest_after=0, description='ding0 open', symbol='k', unicode=0x006b, symbol_description='lowercase k', balifont_symbol_description='dotless i underdot'),
    "l": Note(note=36, duration=1, rest_after=0, description='dong0 open', symbol='l', unicode=0x006c, symbol_description='lowercase l', balifont_symbol_description='o underdot'),
    # "n": Note(note=999, duration=0, rest_after=0, description='norot (always followed by note)', symbol='n', unicode=0x006e, symbol_description='lowercase n', balifont_symbol_description=''),
    "o": Note(note=41, duration=1, rest_after=0, description='dong1 open', symbol='o', unicode=0x006f, symbol_description='lowercase o', balifont_symbol_description='o'),
    "p": Note(note=63, duration=4, rest_after=0, description='pur', symbol='p', unicode=0x0070, symbol_description='lowercase p', balifont_symbol_description='P'),       
    "q": Note(note=49, duration=1, rest_after=0, description='dang2 open', symbol='q', unicode=0x0071, symbol_description='lowercase q', balifont_symbol_description='a overdot'),
    # "r": Note(note=999, duration=1, rest_after=0, description='deung open', symbol='r', unicode=0x0072, symbol_description='lowercase r', balifont_symbol_description=''),   
    # "s": Note(note=999, duration=1, rest_after=0, description='daing open', symbol='s', unicode=0x0073, symbol_description='lowercase s', balifont_symbol_description=''),   
    "t": Note(note=64, duration=4, rest_after=0, description='tong', symbol='t', unicode=0x0074, symbol_description='lowercase t', balifont_symbol_description='T'),      
    "u": Note(note=43, duration=1, rest_after=0, description='dung1 open', symbol='u', unicode=0x0075, symbol_description='lowercase u', balifont_symbol_description='u'),
    "w": Note(note=62, duration=4, rest_after=0, description='gir lanang', symbol='w', unicode=0x0077, symbol_description='lowercase w', balifont_symbol_description='L'),
    "x": Note(note=81, duration=1, rest_after=0, description='tick open', symbol='x', unicode=0x0078, symbol_description='lowercase x', balifont_symbol_description='x'), 
    "y": Note(note=80, duration=1, rest_after=0, description='byong (old notation)', symbol='y', unicode=0x0079, symbol_description='lowercase y', balifont_symbol_description=''),   
    "z": Note(note=39, duration=1, rest_after=0, description='dang0 open', symbol='z', unicode=0x007a, symbol_description='lowercase z', balifont_symbol_description='a underdot'),
    "©": Note(note=70, duration=1, rest_after=0, description='ke open', symbol='©', unicode=0x00a9, symbol_description='copyright', balifont_symbol_description='k'),     
    "ª": Note(note=0, duration=0.25, rest_after=0, description='silence quarter duration', symbol='ª', unicode=0x00aa, symbol_description='underlined a superscript', balifont_symbol_description='dot with double macron'),
    "«": Note(note=72, duration=1, rest_after=0, description='dut open', symbol='«', unicode=0x00ab, symbol_description='left double chevron quote', balifont_symbol_description='d'),
    "¬": Note(note=74, duration=1, rest_after=0, description='krum open', symbol='¬', unicode=0x00ac, symbol_description='logical not', balifont_symbol_description='n'), 
    "®": Note(note=71, duration=1, rest_after=0, description='pak open', symbol='®', unicode=0x00ae, symbol_description='registered trademark', balifont_symbol_description='p'),
    "¯": Note(note=73, duration=1, rest_after=0, description='dut open', symbol='¯', unicode=0x00af, symbol_description='high hyphen', balifont_symbol_description='t'),  
    "°": Note(note=75, duration=1, rest_after=0, description='pung open', symbol='°', unicode=0x00b0, symbol_description='degrees', balifont_symbol_description='u'),     
    "±": Note(note=70, duration=1, rest_after=0, description='ke open', symbol='±', unicode=0x00b1, symbol_description='plusminus', balifont_symbol_description='k'),     
    "²": Note(note=72, duration=1, rest_after=0, description='dut open', symbol='²', unicode=0x00b2, symbol_description='squared (two superscript)', balifont_symbol_description='d'),
    "³": Note(note=74, duration=1, rest_after=0, description='krum open', symbol='³', unicode=0x00b3, symbol_description='cubed (three superscript)', balifont_symbol_description='n'),
    "µ": Note(note=0, duration=0.5, rest_after=0, description='silence half duration', symbol='µ', unicode=0x00b5, symbol_description='mu', balifont_symbol_description='dot with single macron'),
    "¶": Note(note=71, duration=1, rest_after=0, description='pak open', symbol='¶', unicode=0x00b6, symbol_description='at', balifont_symbol_description='p'),
    "·": Note(note=73, duration=1, rest_after=0, description='dut open', symbol='·', unicode=0x00b7, symbol_description='dot', balifont_symbol_description='t'),
    "¸": Note(note=75, duration=1, rest_after=0, description='pung open', symbol='¸', unicode=0x00b8, symbol_description='comma', balifont_symbol_description='u'),       
    "À": Note(note=39, duration=0.1, rest_after=0.4, description='dang0 half duration long muted', symbol='À', unicode=0x00c0, symbol_description='uppercase A grave', balifont_symbol_description='a underdot slashed, single macron'),
    "Á": Note(note=39, duration=0.1, rest_after=0.4, description='dang0 half duration long muted', symbol='Á', unicode=0x00c1, symbol_description='uppercase A acute', balifont_symbol_description='a underdot slashed, single macron'),
    "Â": Note(note=39, duration=0.05, rest_after=0.2, description='dang0 quarter duration muted ', symbol='Â', unicode=0x00c2, symbol_description='uppercase A circumflex', balifont_symbol_description='a underdot slashed, double macron'),
    "Ä": Note(note=44, duration=0.05, rest_after=0.2, description='dang1 quarter duration muted ', symbol='Ä', unicode=0x00c4, symbol_description='uppercase A trema', balifont_symbol_description='a slashed, double macron'),
    "È": Note(note=37, duration=0.1, rest_after=0.4, description='deng0 half duration long muted', symbol='È', unicode=0x00c8, symbol_description='uppercase E grave', balifont_symbol_description='e underdot slashed, single macron'),
    "É": Note(note=42, duration=0.1, rest_after=0.4, description='deng1 half duration long muted', symbol='É', unicode=0x00c9, symbol_description='uppercase E acute', balifont_symbol_description='e slashed, single macron'),
    "Ê": Note(note=37, duration=0.05, rest_after=0.2, description='deng0 quarter duration muted ', symbol='Ê', unicode=0x00ca, symbol_description='uppercase E circumflex', balifont_symbol_description='e underdot slashed, double macron'),
    "Ë": Note(note=42, duration=0.05, rest_after=0.2, description='deng1 quarter duration muted ', symbol='Ë', unicode=0x00cb, symbol_description='uppercase E trema', balifont_symbol_description='e slashed, double macron'),
    "Ì": Note(note=35, duration=0.1, rest_after=0.4, description='ding0 half duration long muted', symbol='Ì', unicode=0x00cc, symbol_description='uppercase I grave', balifont_symbol_description='dotless i underdot slashed, single macron'),
    "Í": Note(note=40, duration=0.1, rest_after=0.4, description='ding1 half duration long muted', symbol='Í', unicode=0x00cd, symbol_description='uppercase I acute', balifont_symbol_description='dotless i slashed, single macron'),
    "Î": Note(note=35, duration=0.05, rest_after=0.2, description='ding0 quarter duration muted ', symbol='Î', unicode=0x00ce, symbol_description='uppercase I circumflex', balifont_symbol_description='dotless i underdot slashed, double macron'),
    "Ï": Note(note=40, duration=0.05, rest_after=0.2, description='ding1 quarter duration muted ', symbol='Ï', unicode=0x00cf, symbol_description='uppercase I trema', balifont_symbol_description='dotless i slashed, double macron'),
    "Ò": Note(note=36, duration=0.1, rest_after=0.4, description='dong0 half duration long muted', symbol='Ò', unicode=0x00d2, symbol_description='uppercase O grave', balifont_symbol_description='o underdot slashed, single macron'),
    "Ó": Note(note=41, duration=0.1, rest_after=0.4, description='dong1 half duration long muted', symbol='Ó', unicode=0x00d3, symbol_description='uppercase O acute', balifont_symbol_description='o slashed, single macron'),
    "Ô": Note(note=36, duration=0.05, rest_after=0.2, description='dong0 quarter duration muted ', symbol='Ô', unicode=0x00d4, symbol_description='uppercase O circumflex', balifont_symbol_description='o underdot slashed, double macron'),
    "Ö": Note(note=41, duration=0.05, rest_after=0.2, description='dong1 quarter duration muted ', symbol='Ö', unicode=0x00d6, symbol_description='uppercase O trema', balifont_symbol_description='o slashed, double macron'),
    "Ù": Note(note=38, duration=0.1, rest_after=0.4, description='dung0 half duration long muted', symbol='Ù', unicode=0x00d9, symbol_description='uppercase U grave', balifont_symbol_description='u underdot slashed, single macron'),
    "Ú": Note(note=43, duration=0.1, rest_after=0.4, description='dung1 half duration long muted', symbol='Ú', unicode=0x00da, symbol_description='uppercase U acute', balifont_symbol_description='u slashed, single macron'),
    "Û": Note(note=38, duration=0.05, rest_after=0.2, description='dung0 quarter duration muted ', symbol='Û', unicode=0x00db, symbol_description='uppercase U circumflex', balifont_symbol_description='u underdot slashed, double macron'),
    "Ü": Note(note=43, duration=0.05, rest_after=0.2, description='dung1 quarter duration muted ', symbol='Ü', unicode=0x00dc, symbol_description='uppercase U trema', balifont_symbol_description='u slashed, double macron'),
    "Ý": Note(note=81, duration=0.1, rest_after=0.4, description='tick half duration long muted', symbol='Ý', unicode=0x00dd, symbol_description='uppercase Y acute', balifont_symbol_description='x slashed, single macron'),
    "à": Note(note=39, duration=0.5, rest_after=0, description='dang0 half duration', symbol='à', unicode=0x00e0, symbol_description='lowercase a grave', balifont_symbol_description='a underdot single macron'),
    "á": Note(note=44, duration=0.5, rest_after=0, description='dang1 half duration', symbol='á', unicode=0x00e1, symbol_description='lowercase a acute', balifont_symbol_description='a single macron'),
    "â": Note(note=44, duration=0.25, rest_after=0, description='dang1 quarter duration', symbol='â', unicode=0x00e2, symbol_description='lowercase a circumflex', balifont_symbol_description='a double macron'),
    "ä": Note(note=44, duration=0.25, rest_after=0, description='dang1 quarter duration', symbol='ä', unicode=0x00e4, symbol_description='lowercase a trema', balifont_symbol_description='a double macron'),
    "è": Note(note=37, duration=0.5, rest_after=0, description='deng0 half duration', symbol='è', unicode=0x00e8, symbol_description='lowercase e grave', balifont_symbol_description='e underdot single macron'),
    "é": Note(note=42, duration=0.5, rest_after=0, description='deng1 half duration', symbol='é', unicode=0x00e9, symbol_description='lowercase e', balifont_symbol_description='e single macron'),
    "ê": Note(note=37, duration=0.25, rest_after=0, description='deng0 quarter duration', symbol='ê', unicode=0x00ea, symbol_description='lowercase e circumflex', balifont_symbol_description='e underdot double macron'),
    "ë": Note(note=42, duration=0.25, rest_after=0, description='deng1 quarter duration', symbol='ë', unicode=0x00eb, symbol_description='lowercase e trema', balifont_symbol_description='e double macron'),
    "ì": Note(note=42, duration=0.5, rest_after=0, description='deng1 half duration', symbol='ì', unicode=0x00ec, symbol_description='lowercase i grave', balifont_symbol_description='e single macron'),
    "í": Note(note=40, duration=0.5, rest_after=0, description='ding1 half duration', symbol='í', unicode=0x00ed, symbol_description='lowercase i', balifont_symbol_description='dotless i single macron'),
    "î": Note(note=35, duration=0.25, rest_after=0, description='ding0 quarter duration', symbol='î', unicode=0x00ee, symbol_description='lowercase i circumflex', balifont_symbol_description='dotless i underdot double macron'),
    "ï": Note(note=40, duration=0.25, rest_after=0, description='ding1 quarter duration', symbol='ï', unicode=0x00ef, symbol_description='lowercase i trema', balifont_symbol_description='dotless i double macron'),
    "ò": Note(note=36, duration=0.25, rest_after=0, description='dong0 quarter duration', symbol='ò', unicode=0x00f2, symbol_description='lowercase o grave', balifont_symbol_description='o underdot double macron'),
    "ó": Note(note=41, duration=0.5, rest_after=0, description='dong1 half duration', symbol='ó', unicode=0x00f3, symbol_description='lowercase o', balifont_symbol_description='o single macron'),
    "ô": Note(note=36, duration=0.25, rest_after=0, description='dong0 quarter duration', symbol='ô', unicode=0x00f4, symbol_description='lowercase o circumflex', balifont_symbol_description='o underdot double macron'),
    "ö": Note(note=41, duration=0.25, rest_after=0, description='dong1 quarter duration', symbol='ö', unicode=0x00f6, symbol_description='lowercase o trema', balifont_symbol_description='o double macron'),
    "ù": Note(note=38, duration=0.5, rest_after=0, description='dung0 half duration', symbol='ù', unicode=0x00f9, symbol_description='lowercase u grave', balifont_symbol_description='u underdot single macron'),
    "ú": Note(note=43, duration=0.5, rest_after=0, description='dung1 half duration', symbol='ú', unicode=0x00fa, symbol_description='lowercase u acute', balifont_symbol_description='u single macron'),
    "û": Note(note=38, duration=0.25, rest_after=0, description='dung0 quarter duration', symbol='û', unicode=0x00fb, symbol_description='lowercase u circumflex', balifont_symbol_description='u underdot double macron'),
    "ü": Note(note=43, duration=0.25, rest_after=0, description='dung1 quarter duration', symbol='ü', unicode=0x00fc, symbol_description='lowercase u trema', balifont_symbol_description='u double macron'),
    "ý": Note(note=81, duration=0.5, rest_after=0, description='tick half duration', symbol='ý', unicode=0x00fd, symbol_description='lowercase y acute', balifont_symbol_description='x single macron'),
    "ÿ": Note(note=81, duration=0.25, rest_after=0, description='tick quarter duration', symbol='ÿ', unicode=0x00ff, symbol_description='lowercase y trema', balifont_symbol_description='x double macron'),
    "Ā": Note(note=49, duration=0.1, rest_after=0.4, description='dang2 half duration long muted', symbol='Ā', unicode=0x0100, symbol_description='uppercase A macron', balifont_symbol_description='a overdot slashed, single macron'),
    "ā": Note(note=49, duration=0.5, rest_after=0, description='dang2 half duration', symbol='ā', unicode=0x0101, symbol_description='lowercase a macron', balifont_symbol_description='a overdot single macron'),
    "Ă": Note(note=49, duration=0.05, rest_after=0.2, description='dang2 quarter duration muted ', symbol='Ă', unicode=0x0102, symbol_description='uppercase A breve', balifont_symbol_description='a overdot slashed, double macron'),
    "ă": Note(note=49, duration=0.25, rest_after=0, description='dang2 quarter duration', symbol='ă', unicode=0x0103, symbol_description='lowercase a breve', balifont_symbol_description='a overdot double macron'),
    "Ē": Note(note=47, duration=0.1, rest_after=0.4, description='deng2 half duration long muted', symbol='Ē', unicode=0x0112, symbol_description='uppercase E macron', balifont_symbol_description='e overdot slashed, single macron'),
    "ē": Note(note=47, duration=0.5, rest_after=0, description='deng2 half duration', symbol='ē', unicode=0x0113, symbol_description='lowercase e macron', balifont_symbol_description='e overdot single macron'),
    "Ĕ": Note(note=47, duration=0.05, rest_after=0.2, description='deng2 quarter duration muted ', symbol='Ĕ', unicode=0x0114, symbol_description='uppercase E breve', balifont_symbol_description='e overdot slashed, double macron'),
    "ĕ": Note(note=47, duration=0.25, rest_after=0, description='deng2 quarter duration', symbol='ĕ', unicode=0x0115, symbol_description='lowercase e breve', balifont_symbol_description='e overdot double macron'),
    "Ī": Note(note=45, duration=0.1, rest_after=0.4, description='ding2 half duration long muted', symbol='Ī', unicode=0x012a, symbol_description='uppercase i macron', balifont_symbol_description='i (with dot) slashed, single macron'),
    "ī": Note(note=45, duration=0.5, rest_after=0, description='ding2 half duration', symbol='ī', unicode=0x012b, symbol_description='lowercase i macron', balifont_symbol_description='i (with dot) single macron'),
    "Ĭ": Note(note=45, duration=0.05, rest_after=0.2, description='ding2 quarter duration muted ', symbol='Ĭ', unicode=0x012c, symbol_description='uppercase I breve', balifont_symbol_description='i (with dot) slashed, double macron'),
    "ĭ": Note(note=45, duration=0.25, rest_after=0, description='ding2 quarter duration', symbol='ĭ', unicode=0x012d, symbol_description='lowercase i breve', balifont_symbol_description='i (with dot) double macron'),
    "Ō": Note(note=46, duration=0.1, rest_after=0.4, description='dong2 half duration long muted', symbol='Ō', unicode=0x014c, symbol_description='uppercase O macron', balifont_symbol_description='o overdot slashed, single macron'),
    "ō": Note(note=46, duration=0.5, rest_after=0, description='dong2 half duration', symbol='ō', unicode=0x014d, symbol_description='lowercase o macron', balifont_symbol_description='o overdot single macron'),
    "Ŏ": Note(note=46, duration=0.05, rest_after=0.2, description='dong2 quarter duration muted ', symbol='Ŏ', unicode=0x014e, symbol_description='uppercase O breve', balifont_symbol_description='o overdot slashed, double macron'),
    "ŏ": Note(note=46, duration=0.25, rest_after=0, description='dong2 quarter duration', symbol='ŏ', unicode=0x014f, symbol_description='lowercase o breve', balifont_symbol_description='o overdot double macron'),
    # "Ŕ": Note(note=999, duration=0.1, rest_after=0.4, description='deung half duration muted', symbol='Ŕ', unicode=0x0154, symbol_description='uppercase R acute', balifont_symbol_description=''),
    # "ŕ": Note(note=999, duration=0.5, rest_after=0, description='deung open half duration', symbol='ŕ', unicode=0x0155, symbol_description='lowercase r acute', balifont_symbol_description=''),
    # "Ŗ": Note(note=999, duration=0.05, rest_after=0.2, description='deung quarter duration muted', symbol='Ŗ', unicode=0x0156, symbol_description='uppercase R undercomma', balifont_symbol_description=''),
    # "ŗ": Note(note=999, duration=0.25, rest_after=0, description='deung open quarter duration', symbol='ŗ', unicode=0x0157, symbol_description='lowercase r undercomma', balifont_symbol_description=''),
    # "Ś": Note(note=999, duration=0.1, rest_after=0.4, description='daing half duration muted', symbol='Ś', unicode=0x015a, symbol_description='uppercase S acute', balifont_symbol_description=''),
    # "ś": Note(note=999, duration=0.5, rest_after=0, description='daing open half duration', symbol='ś', unicode=0x015b, symbol_description='lowercase s acute', balifont_symbol_description=''),
    # "Ş": Note(note=999, duration=0.05, rest_after=0.2, description='daing quarter duration muted', symbol='Ş', unicode=0x015e, symbol_description='uppercase S cedille', balifont_symbol_description=''),
    # "ş": Note(note=999, duration=0.25, rest_after=0, description='daing open quarter duration', symbol='ş', unicode=0x015f, symbol_description='lowercase s cedille', balifont_symbol_description=''),
    "Ū": Note(note=48, duration=0.1, rest_after=0.4, description='dung2 half duration long muted', symbol='Ū', unicode=0x016a, symbol_description='uppercase U macron', balifont_symbol_description='u overdot slashed, single macron'),
    "ū": Note(note=48, duration=0.5, rest_after=0, description='dung2 half duration', symbol='ū', unicode=0x016b, symbol_description='lowercase u macron', balifont_symbol_description='u overdot single macron'),
    "Ŭ": Note(note=48, duration=0.05, rest_after=0.2, description='dung2 quarter duration muted ', symbol='Ŭ', unicode=0x016c, symbol_description='uppercase U breve', balifont_symbol_description='u overdot slashed, double macron'),
    "ŭ": Note(note=48, duration=0.25, rest_after=0, description='dung2 quarter duration', symbol='ŭ', unicode=0x016d, symbol_description='lowercase u breve', balifont_symbol_description='u overdot double macron'),
    "Ÿ": Note(note=81, duration=0.05, rest_after=0.2, description='tick quarter duration muted ', symbol='Ÿ', unicode=0x0178, symbol_description='uppercase Y trema', balifont_symbol_description='x slashed, double macron'),
    # "Ž": Note(note=999, duration=1, rest_after=0, description='long mutes previous note, half duration', symbol='Ž', unicode=0x017d, symbol_description='uppercase Z caron', balifont_symbol_description=''),
    # "ž": Note(note=999, duration=1, rest_after=0, description='long mutes previous note, quarter duration', symbol='ž', unicode=0x017e, symbol_description='lowercase Z caron', balifont_symbol_description=''),
}
# fmt: on

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
