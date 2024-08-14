from mido import Message, MidiTrack

from src.common.classes import Character, Score
from src.common.constants import InstrumentPosition, NotationFont, SymbolValue
from src.common.utils import SYMBOLVALUE_TO_MIDINOTE_LOOKUP
from src.notation2midi.settings import BASE_NOTE_TIME


class MidiTrackX(MidiTrack):
    font: NotationFont
    last_note_end_msg = None
    time_since_last_note_end = 0

    def __init__(self, font: NotationFont):
        self.font = font
        super(MidiTrackX, self).__init__()

    def process(self, position: InstrumentPosition, note: Character):
        if self.font is NotationFont.BALIMUSIC4:
            self.process_font4(position, note)
        elif self.font is NotationFont.BALIMUSIC5:
            self.process_font5(position, note)
        else:
            raise ValueError(f"Unexpected font value {self.font}")

    def process_font4(self, position: InstrumentPosition, note: Character):
        """Converts a note into a midi event

        Args:
            position (InstrumentPosition): The instrument position playing the note.
            note (Character): Note to be processed.

        Raises:
            ValueError: _description_
        """
        if not note.value.is_nonnote:
            midinote = SYMBOLVALUE_TO_MIDINOTE_LOOKUP[position.instrumenttype, note.value]
            # Set ON and OFF messages for actual note
            self.append(
                Message(
                    type="note_on",
                    channel=midinote.channel,
                    note=midinote.midi,
                    velocity=100,
                    time=self.time_since_last_note_end,
                )
            )
            self.append(
                Message(
                    type="note_off",
                    channel=midinote.channel,
                    note=midinote.midi,
                    velocity=70,
                    time=int(note.duration * BASE_NOTE_TIME),
                )
            )
            self.last_note_end_msg = self[-1]
            self.time_since_last_note_end = int(note.rest_after * BASE_NOTE_TIME)
        elif note.value is SymbolValue.SILENCE:
            # Increment time since last note ended
            self.time_since_last_note_end += int(note.duration * BASE_NOTE_TIME)
        elif note.value is SymbolValue.EXTENSION:
            # Extension of note duration: add duration to last note
            if self.last_note_end_msg:
                self.last_note_end_msg.time += int(note.duration * BASE_NOTE_TIME)
        else:
            raise ValueError(f"Unexpected note value {note.value}")

    def process_font5(self, position: InstrumentPosition, note: Character):
        pass


def postprocess_font4(score: Score) -> Score:
    # Merge notes with negative value with previous note(s)
    for system in score.systems:
        for beat in system.beats:
            for instrument, stave in beat.staves.items():
                stave_cpy = stave.copy()
                stave.clear()
                for note in stave_cpy:
                    if note.value is SymbolValue.MODIFIER_PREV1:
                        prevnote = stave.pop(-1)
                        stave.append(
                            prevnote.model_copy(update={"duration": note.duration, "rest_after": note.rest_after})
                        )
                    elif note.value is SymbolValue.MODIFIER_PREV2:
                        prev1note = stave.pop(-1)
                        prev2note = stave.pop(-1)
                        stave.append(prev2note.model_copy(update={"duration": note.duration}))
                        stave.append(prev1note.model_copy(update={"duration": note.rest_after}))
                    else:
                        stave.append(note)
            beat.duration = max(sum(note.total_duration for note in notes) for notes in list(beat.staves.values()))


def postprocess_font5(score: Score) -> Score:
    for system in score.systems:
        for beat in system.beats:
            for instrument, stave in beat.staves.items():
                stave_cpy = stave.copy()
                stave.clear()
                for note in stave_cpy:
                    if note.value is SymbolValue.MODIFIER_PREV1:
                        prevnote = stave.pop(-1)
                        stave.append(
                            prevnote.model_copy(update={"duration": note.duration, "rest_after": note.rest_after})
                        )
                    elif note.value is SymbolValue.MODIFIER_PREV2:
                        prev1note = stave.pop(-1)
                        prev2note = stave.pop(-1)
                        stave.append(prev2note.model_copy(update={"duration": note.duration}))
                        stave.append(prev1note.model_copy(update={"duration": note.rest_after}))
                    else:
                        stave.append(note)
            beat.duration = max(sum(note.total_duration for note in notes) for notes in list(beat.staves.values()))


def postprocess(score: Score) -> Score:
    if score.source.font is NotationFont.BALIMUSIC4:
        postprocess_font4(score)
    elif score.source.font is NotationFont.BALIMUSIC5:
        postprocess_font5(score)
    else:
        raise ValueError(f"Unexpected font value {score.source.font}")
