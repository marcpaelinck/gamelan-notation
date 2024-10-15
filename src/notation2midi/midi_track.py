from mido import Message, MetaMessage, MidiTrack, bpm2tempo

from src.common.classes import Note
from src.common.constants import (
    InstrumentPosition,
    InstrumentType,
    NotationFont,
    Pitch,
    Stroke,
)
from src.common.lookups import get_bank_mido, get_channel_mido, get_preset_mido
from src.common.utils import SYMBOLVALUE_TO_MIDINOTE_LOOKUP
from src.settings.settings import BASE_NOTE_TIME, BASE_NOTES_PER_BEAT


class MidiTrackX(MidiTrack):
    position: InstrumentPosition
    font: NotationFont
    last_note_end_msg = None
    time_since_last_note_end: int = 0
    current_bpm: int = 0
    current_signature: int = 0

    def set_channel_bank_and_preset(self):
        channel = get_channel_mido(self.position.instrumenttype)
        bank = get_bank_mido(self.position.instrumenttype)
        preset = get_preset_mido(self.position.instrumenttype)
        self.append(MetaMessage("channel_prefix", channel))
        self.append(Message(type="control_change", control=0, value=bank))
        self.append(Message(type="program_change", program=preset))

    def __init__(self, position: InstrumentPosition, font: NotationFont):
        super(MidiTrackX, self).__init__()
        self.font = font
        self.position = position
        self.set_channel_bank_and_preset()

    def total_tick_time(self):
        return sum(msg.time for msg in self)

    # def update_signature(self, new_signature) -> None:
    #     if new_signature != self.current_signature:
    #         self.append(
    #             MetaMessage(
    #                 "time_signature",
    #                 numerator=round(new_signature),
    #                 denominator=4,
    #                 clocks_per_click=36,
    #                 notated_32nd_notes_per_beat=8,
    #                 time=self.time_since_last_note_end,
    #             )
    #         )
    #         self.time_since_last_note_end = 0
    #         self.current_signature = new_signature

    def update_tempo(self, new_bpm, debug=False):
        if debug:
            print(f"     midi_track: request received to change bpm to {new_bpm}, current bpm={self.current_bpm}")
        if new_bpm != self.current_bpm:
            if debug:
                print(f"                 setting metamessage with new tempo {new_bpm}")
            self.append(MetaMessage("set_tempo", tempo=bpm2tempo(new_bpm)))
            self.current_bpm = new_bpm

    def extend_last_note(self, seconds: int) -> None:
        if self.last_note_end_msg:
            beats = round(self.current_bpm * seconds / 60)
            self.last_note_end_msg.time += beats * BASE_NOTE_TIME * BASE_NOTES_PER_BEAT

    def add_note(self, position: InstrumentPosition, character: Note):
        """Converts a note into a midi event

        Args:
            position (InstrumentPosition): The instrument position playing the note.
            note (Character): Note to be processed.

        Raises:
            ValueError: _description_
        """
        if not character.pitch == Pitch.NONE:
            midinote = SYMBOLVALUE_TO_MIDINOTE_LOOKUP[
                position.instrumenttype, character.pitch, character.octave, character.stroke
            ]
            # Set ON and OFF messages for actual note
            self.append(
                Message(
                    type="note_on",
                    note=midinote.midinote,
                    velocity=character.velocity,
                    time=self.time_since_last_note_end,
                )
            )
            self.append(
                Message(
                    type="note_off",
                    note=midinote.midinote,
                    velocity=70,
                    time=round(character.duration * BASE_NOTE_TIME),
                )
            )
            self.last_note_end_msg = self[-1]
            self.time_since_last_note_end = round(character.rest_after * BASE_NOTE_TIME)
        # TODO next two ifs can now be combined
        elif character.stroke is Stroke.SILENCE:
            # Increment time since last note ended
            self.time_since_last_note_end += round(character.rest_after * BASE_NOTE_TIME)
        elif character.stroke is Stroke.EXTENSION:
            # Extension of note duration: add duration to last note
            # If a SILENCE occurred previously, treat the EXTENSION as a SILENCE
            if self.last_note_end_msg and self.time_since_last_note_end == 0:
                self.last_note_end_msg.time += round(character.duration * BASE_NOTE_TIME)
            else:
                self.time_since_last_note_end += round(character.duration * BASE_NOTE_TIME)
        else:
            raise ValueError(f"Unexpected note value {character.pitch} {character.octave} {character.stroke}")
