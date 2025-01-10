import json
import re
from collections import defaultdict

from src.common.classes import InstrumentTag, Notation, Note
from src.common.constants import (
    DEFAULT,
    InstrumentGroup,
    NotationDict,
    NotationFont,
    Octave,
    Pitch,
    Position,
    SpecialTags,
    Stroke,
)
from src.common.metadata_classes import MetaData, Scope
from src.notation2midi.classes import ParserModel
from src.settings.classes import RunSettings
from src.settings.settings import BASE_NOTE_TIME, get_run_settings

# ==================== BALI MUSIC 5 FONT =====================================


class Notation5Parser(ParserModel):
    run_settings: RunSettings
    notation_lines: list[str]
    curr_position: int

    TREMOLO_NR_OF_NOTES_PER_QUARTERNOTE: int = 3  # should be a divisor of BASE_NOTE_TIME
    # Next values are in 1/BASE_NOTE_TIME. E.g. if BASE_NOTE_TIME=24, then 24 is a standard note duration.
    # Should also be an even number so that alternating note patterns end on the second note.
    TREMOLO_ACCELERATING_PATTERN: list[int] = [48, 40, 32, 26, 22, 18, 14, 10, 10, 10, 10, 10]
    TREMOLO_ACCELERATING_VELOCITY: list[int] = [100] * (len(TREMOLO_ACCELERATING_PATTERN) - 5) + [90, 80, 70, 60, 50]

    def __init__(self, run_settings: RunSettings):
        super().__init__(self.ParserType.NOTATIONPARSER, run_settings)
        self.run_settings = run_settings
        with open(run_settings.notation.filepath, "r") as input:
            self.notation_lines = [line.rstrip() for line in input]

    def _passes_str_to_list(self, rangestr: str) -> list[int]:
        """Converts a pass indicator following a position tag to a list of passes.
            A colon (:) separates the position tag and the pass indicator.
            The indicator has one of the following formats:
            <pass>[,<pass>...]
            <firstpass>-<lastpass>
            where <pass>, <firstpass> and <lastpass> are single digits.
            e.g.:
            gangsa p:2,3

        Args:
            rangestr (str): the pass range indicator, in the prescribed format.

        Raises:
            ValueError: string does not have the expected format.

        Returns:
            list[int]: a list of passes (passes are numbered from 1)
        """
        if not re.match(r"^(\d-\d|(\d,)*\d)$", rangestr):
            raise ValueError(f"Invalid value for passes: {rangestr}")
        if re.match(r"^\d-\d$", rangestr):
            return list(range(int(rangestr[0]), int(rangestr[2]) + 1))
        else:
            return list(json.loads(f"[{rangestr}]"))

    def _generate_tremolo(self, notes: list[Note]) -> list[Note]:
        """Generates the note sequence for a tremolo.
         TREMOLO: The duration and pitch will be that of the given note.
         TREMOLO_ACCELERATING: The pitch will be that of the given note(s), the duration will be derived
         from the TREMOLO_ACCELERATING_PATTERN.

        Args:
            notes (list[Note]): One or two notes on which to base the tremolo (piitch only)

        Returns:
            list[Note]: The resulting notes
        """
        tremolo_notes = []

        if notes[0].stroke is Stroke.TREMOLO:
            note = notes[0]
            nr_of_notes = round(note.duration * self.TREMOLO_NR_OF_NOTES_PER_QUARTERNOTE)
            duration = note.duration / nr_of_notes
            for _ in range(nr_of_notes):
                tremolo_notes.append(note.model_copy(update={"duration": duration}))
        elif notes[0].stroke is Stroke.TREMOLO_ACCELERATING:
            durations = [i / BASE_NOTE_TIME for i in self.TREMOLO_ACCELERATING_PATTERN]
            note_idx = 0
            for duration, velocity in zip(durations, self.TREMOLO_ACCELERATING_VELOCITY):
                tremolo_notes.append(notes[note_idx].model_copy(update={"duration": duration, "velocity": velocity}))
                note_idx = (note_idx + 1) % len(notes)
        else:
            self.logerror(f"Unexpected tremolo type {notes[0].stroke}.")

        return tremolo_notes

    def _parse_stave(self, stave: str, position: Position) -> list[Note]:
        """Parses the notation of a stave to note objects

        Args:
            stave (str): one stave of notation
            position (Position):

        Returns: str | None: _description_
        """
        notes = []  # will contain the Note objects
        tremolo_notes = []
        note_chars = stave
        while note_chars:
            # try parsing the next note
            next_note = Note.parse_next_note(note_chars, position)
            if not next_note:
                self.logerror(f" {position.value} {stave} has invalid {note_chars[0]}")
                note_chars = note_chars[1:]
            else:
                if istremolo := (next_note.stroke in (Stroke.TREMOLO, Stroke.TREMOLO_ACCELERATING)):
                    tremolo_notes.append(next_note)
                if len(tremolo_notes) == 2 or (
                    tremolo_notes and (not istremolo or len(note_chars) == len(next_note.symbol))
                ):
                    notes.extend(self._generate_tremolo(tremolo_notes))
                    tremolo_notes.clear()
                if not istremolo:
                    notes.append(next_note)
                note_chars = note_chars[len(next_note.symbol) :]

        return notes

    def _parse_special_tag(self, tag: SpecialTags, content: str) -> list[str | MetaData]:

        # Check the tag. Return comments without further processing.
        match tag:
            case SpecialTags.COMMENT:
                return content
            case SpecialTags.METADATA:
                pass
            case _:
                self.logerror("Unrecognized tag {tag}")
                return None

        # Try to parse the string value
        try:
            metadata = MetaData(data=content)
        except Exception as err:
            # The validation and generation of meaningful error messages is performed in the MetaData class.
            msg = (
                ". ".join(arg for arg in err.args if arg)
                if err.args
                else str(err.errors()[0]["msg"]).replace("\n", ".")
            )
            self.logerror(f"{content} - {msg}")

            return None

        return metadata

    def _get_nearest_note(self, note: Note, other_note: Note) -> Note:
        """Returns the octave for note that minimizes the distance between the two note pitches.

        Args:
            note (Note): note for which to optimize the octave
            other_note (Note): reference nte
            noterange (list[tuple[Pitch, Octave]]): available note range

        Returns:
            Octave: the octave that puts the pitch of note nearest to that of other_note
        """

        # Nothing if either note is non-melodic (reyong can have both types of notes)
        if not note.octave or not other_note.octave:
            return note

        def index(note: Note) -> int:
            noterange = (
                [Pitch.DING, Pitch.DONG, Pitch.DENG, Pitch.DEUNG, Pitch.DUNG, Pitch.DANG, Pitch.DAING]
                if self.run_settings.instruments.instrumentgroup == InstrumentGroup.SEMAR_PAGULINGAN
                else [Pitch.DING, Pitch.DONG, Pitch.DENG, Pitch.DUNG, Pitch.DANG]
            )
            return noterange.index(note.pitch) + len(noterange) * note.octave

        if not note.pitch or not other_note.pitch or other_note.octave == None:
            raise Exception(f"Can't set octave for grace note {note}")

        next_note_idx = index(other_note)
        nearest_note = None
        best_distance = 999
        for offset in [0, 1, -1]:
            new_octave = other_note.octave + offset
            if (try_note := note.model_copy(update={"octave": new_octave})) and (
                new_distance := abs(index(try_note) - next_note_idx)
            ) < best_distance:
                best_distance = min(new_distance, best_distance)
                nearest_note = try_note
        return nearest_note

    def _update_grace_notes(self, notation_dict: NotationDict):
        """Modifies the octave of all the grace notes to match the not that follows.
        The octave is set to minimise the 'distance' between both notes.
        Args:
            notation_dict (NotationDict): The notation
        """
        for self.curr_gongan_id, beat_dict in notation_dict.items():
            for self.curr_beat_id, staves in beat_dict.items():
                if not isinstance(self.curr_beat_id, int):
                    continue
                for position, stave in staves.items():
                    for pass_, notes in stave.items():
                        for note, nextnote in zip(notes.copy(), notes.copy()[1:]):
                            if note.stroke == Stroke.GRACE_NOTE:
                                new_note = self._get_nearest_note(note=note, other_note=nextnote)
                                notes[notes.index(note)] = new_note

    def parse_notation(self) -> tuple[NotationDict, list[Position]]:
        """Parses a notation file into a dict.

        Returns:
            NotationDict: A dict notation[gongan_id][beat_id][position][passes] that has been validated on notation syntaxis.
            The dict can be further processed into a Score object model.
        """
        notation_dict = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
        notation_dict[DEFAULT][SpecialTags.METADATA] = list()  # Will contain metadata having scope==Scope.SCORE
        new_gongan = True
        self.curr_gongan_id = 0
        prev_staves = defaultdict(list)

        for self.curr_line_nr, line in enumerate(self.notation_lines, 1):
            # remove trailing tabs and split the line on the remaining tabs.
            line = re.sub(r"\t+$", "", line).split("\t")

            tag = line[0]
            # Skip empty lines
            match tag:
                case "":
                    if len(line) > 1:
                        self.logerror(f"line {self.curr_line_nr} has content but has no label in the first position.")
                    new_gongan = True
                    continue
                case _:
                    if new_gongan:
                        self.curr_gongan_id += 1
                        # Metadata and comments are stored on gongan level
                        notation_dict[self.curr_gongan_id][SpecialTags.METADATA] = []
                        notation_dict[self.curr_gongan_id][SpecialTags.COMMENT] = []
                        new_gongan = False

            # Process metadata and notation
            match tag:
                case SpecialTags.METADATA | SpecialTags.COMMENT:
                    parsed = self._parse_special_tag(tag, content=line[1])
                    if isinstance(parsed, MetaData) and parsed.data.scope == Scope.SCORE:
                        notation_dict[DEFAULT][SpecialTags.METADATA].append(parsed)
                    else:
                        notation_dict[self.curr_gongan_id][tag].append(parsed)

                    continue
                case _:
                    # NOTATION DATA
                    # Check if tag is followed by a pass indicator
                    if len(tag.split(":")) == 2:
                        pos, pass_ = tag.split(":")
                        if not pass_.isnumeric():
                            self.logerror(f"invalid pass number after colon in {tag}.")
                            continue
                        pass_ = int(pass_)
                    else:
                        pos, pass_ = tag, DEFAULT

                    if len(line) > 1:
                        if not InstrumentTag.get_positions(pos):
                            self.logerror(f"unrecognized instrument tag {pos}.")
                            continue

                        positions = InstrumentTag.get_positions(pos)
                        for self.curr_beat_id in range(1, len(line)):
                            for self.curr_position in positions:
                                if line[self.curr_beat_id]:
                                    new_stave = self._parse_stave(
                                        stave=line[self.curr_beat_id], position=self.curr_position
                                    )
                                    notation_dict[self.curr_gongan_id][self.curr_beat_id][self.curr_position][
                                        pass_
                                    ] = new_stave
                                    if pass_ == DEFAULT:
                                        prev_staves[self.curr_position] = notation_dict[self.curr_gongan_id][
                                            self.curr_beat_id
                                        ][self.curr_position][
                                            DEFAULT
                                        ]  # curr_stave becomes the new prev_stave
                                else:
                                    # Create an empty beat. This  ensures a correct ordering of the beats.
                                    # (notation_dict is a defaultdict)
                                    notation_dict[self.curr_gongan_id][self.curr_beat_id]

        # Set the octave of each grace note to minimize the 'distance' to the following note
        self._update_grace_notes(notation_dict)

        if self.has_errors:
            self.logger.error("Program halted.")
            exit()

        notation = Notation(notation_dict=notation_dict, settings=self.run_settings)

        return notation


# ==================== GENERAL CODE =====================================


def get_parser(run_settings: RunSettings):
    if run_settings.font.fontversion is NotationFont.BALIMUSIC5:
        return Notation5Parser(run_settings)
    else:
        raise NotImplementedError(f"No parser available for font {run_settings.font.fontversion}.")


if __name__ == "__main__":
    run_settings = get_run_settings()
    parser = Notation5Parser(run_settings)
    notation = parser.parse_notation()
