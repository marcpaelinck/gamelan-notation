from mido import Message, MetaMessage, MidiTrack, bpm2tempo, tempo2bpm

from src.common.classes import Note, Preset
from src.common.constants import InstrumentType, Pitch, Position, Stroke
from src.common.logger import get_logger
from src.common.lookups import LOOKUP
from src.settings.settings import BASE_NOTE_TIME, BASE_NOTES_PER_BEAT

logger = get_logger(__name__)


class MidiTrackX(MidiTrack):
    name: str
    position: Position
    instrumenttype: InstrumentType
    channel: int
    port: int
    bank: int
    preset: int
    PPQ: int  # pulses per quarternote
    # The next attribute keeps track of the end message of the last note.
    # The time of this message will be delayed if an extension character is encountered.
    last_noteoff_msg = None
    time_since_last_note_end: int = 0
    current_bpm: int = 0
    current_velocity: int = LOOKUP.DYNAMICS_TO_VELOCITY[LOOKUP.DEFAULT_DYNAMICS]
    current_signature: int = 0

    def set_channel_bank_and_preset(self):
        # The rack_name message is auto-generated by the MidiTrack constructor.
        # self.append(MetaMessage("track_name", name=self.name, time=0))
        self.append(MetaMessage(type="midi_port", port=self.port))
        # Note: MSB (control 0) seems to accept values larger than 127.
        self.append(Message(type="control_change", skip_checks=True, control=0, value=self.bank, channel=self.channel))
        self.append(Message(type="program_change", program=self.preset, channel=self.channel))
        # Do not set channel volume. It will be set in the online MIDI app.
        # self.append(
        #     Message(type="control_change", control=7, value=127 if self.channel > 4 else 127, channel=self.channel)
        # )

    def __init__(self, position: Position, preset: Preset, ppq: int):
        super(MidiTrackX, self).__init__()
        self.name = position.value
        self.position = position
        self.channel = preset.channel
        self.port = preset.port
        self.bank = preset.bank
        self.preset = preset.preset
        self.PPQ = ppq
        self.set_channel_bank_and_preset()
        # logger.info(f"Track {self.name}: channel {self.channel}, bank {self.bank}, preset {self.preset}")

    def total_tick_time(self):
        return sum(msg.time for msg in self)

    def current_time_in_millis(self):
        time_in_millis = 0
        bpm = 120
        for msg in self:
            if isinstance(msg, MetaMessage) and msg.type == "set_tempo":
                bpm = tempo2bpm(msg.tempo)
            time_in_millis += msg.time * 60000 / (bpm * self.PPQ)
        return time_in_millis

    def update_tempo(self, new_bpm, debug=False):
        if debug:
            logger.info(f"     midi_track: request received to change bpm to {new_bpm}, current bpm={self.current_bpm}")
        if new_bpm != self.current_bpm:
            if debug:
                logger.info(f"                 setting metamessage with new tempo {new_bpm}")
            self.append(MetaMessage("set_tempo", tempo=bpm2tempo(new_bpm), time=self.time_since_last_note_end))
            self.time_since_last_note_end = 0
            self.current_bpm = new_bpm

    def update_dynamics(self, new_velocity):
        self.current_velocity = new_velocity

    def extend_last_note(self, seconds: int) -> None:
        if self.last_noteoff_msg:
            beats = round(self.current_bpm * seconds / 60)
            self.last_noteoff_msg.time += beats * BASE_NOTE_TIME * BASE_NOTES_PER_BEAT

    def comment(self, message: str) -> None:
        self.append(MetaMessage("text", text=message))

    def marker(self, message: str) -> None:
        self.append(MetaMessage("marker", text=message))

    def add_note(self, character: Note):
        """Converts a note into a midi event

        Args:
            position (Position): The instrument position playing the note.
            note (Character): Note to be processed.

        Raises:
            ValueError: _description_
        """
        if not character.pitch == Pitch.NONE:
            # Set ON and OFF messages for actual note
            # In case of multiple midi notes, all notes should start and stop at the same time.
            for count, midivalue in enumerate(character.midinote):
                self.append(
                    Message(
                        type="note_on",
                        note=midivalue,
                        velocity=self.current_velocity,
                        time=self.time_since_last_note_end if count == 0 else 0,  # all notes start together
                        channel=self.channel,
                    )
                )
            for count, midivalue in enumerate(character.midinote):
                self.append(
                    off_msg := Message(
                        type="note_off",
                        note=midivalue,
                        # velocity=self.current_velocity,
                        time=round(character.duration * BASE_NOTE_TIME) if count == 0 else 0,  # all notes end together
                        channel=self.channel,
                    )
                )
                if count == 0:
                    # If the character corresponds with more than one MIDI note (e.g. reyong `byong`),
                    # we keep track of the note_off message of the first of these notes.
                    # If the combined note needs to be extended, we should only delay
                    # the note-off message of this first note.
                    self.last_noteoff_msg = off_msg

            self.time_since_last_note_end = round(character.rest_after * BASE_NOTE_TIME)
        # TODO next two ifs can now be combined
        elif character.stroke is Stroke.SILENCE:
            # Increment time since last note ended
            self.time_since_last_note_end += round(character.rest_after * BASE_NOTE_TIME)
            self.last_noteoff_msg = None
        elif character.stroke is Stroke.EXTENSION:
            # Extension of note duration: add duration to last note
            # If a SILENCE occurred previously, treat the EXTENSION as a SILENCE
            if self.last_noteoff_msg and self.time_since_last_note_end == 0:
                self.last_noteoff_msg.time += round(character.duration * BASE_NOTE_TIME)
            else:
                self.time_since_last_note_end += round(character.duration * BASE_NOTE_TIME)
        else:
            raise ValueError(f"Unexpected note value {character.pitch} {character.octave} {character.stroke}")
