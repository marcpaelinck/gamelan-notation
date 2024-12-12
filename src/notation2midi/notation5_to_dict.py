import json
import re
from collections import defaultdict

from src.common.classes import Notation, Note, ParserModel, RunSettings, Score
from src.common.constants import (
    DEFAULT,
    NotationDict,
    NotationFont,
    Octave,
    Pitch,
    Position,
    SpecialTags,
    Stroke,
)
from src.common.lookups import LOOKUP
from src.common.metadata_classes import MetaData, Scope
from src.common.playercontent_classes import Part
from src.settings.settings import BASE_NOTE_TIME, get_run_settings

# ==================== BALI MUSIC 5 FONT =====================================


class Font5Parser(ParserModel):
    run_settings: RunSettings
    notation_lines: list[str]
    curr_position: int

    TREMOLO_NR_OF_NOTES_PER_QUARTERNOTE: int = 3  # should be a divisor of BASE_NOTE_TIME
    # Next values are in 1/BASE_NOTE_TIME. E.g. if BASE_NOTE_TIME=24, then 24 is a standard note duration.
    # Should also be an even number so that alternating note patterns end on the second note.
    TREMOLO_ACCELERATING_PATTERN: list[int] = [48, 40, 32, 26, 22, 18, 14, 10, 10, 10, 10, 10]
    TREMOLO_ACCELERATING_VELOCITY: list[int] = [100] * (len(TREMOLO_ACCELERATING_PATTERN) - 5) + [90, 80, 70, 60, 50]

    NOTATION_PATTERNS = [
        # For the tremolo, we could have used r"([aeiours][,<]{0,1}[;]){1,2}" but in case of two successive tremolo notes
        # this string does not yield the two separate sets of <note-char><tremolo-car> as would be expected.
        r"([aeiours][,<]{0,1}[;])([aeiours][,<]{0,1}[;]){0,1}",  # one or two occurrences of a melodic note followed by an optional octave and a tremolo symbols.
        r"([aeiours][,<]{0,1}[:])([aeiours][,<]{0,1}[:]){0,1}",  # same for accelerating tremolo
        r"[kxytb089\(\)\*][:;]",  # non-melodic note followed by a tremolo symbol.
        r"[aeiours][,<]{0,1}[_=]{0,1}[/?]{0,1}",  # melodic note symbol optionally followed by octave symbol, note duration modifier and/or mute/abbrev symbol
        r"[kxytbkxytb089\(\)\*][_=]{0,1}[/?]{0,1}",  # non-melodic symbol optionally followed by note duration modifier and/or mute/abbrev symbol
        r"[AEIOU](?=[aeiou])",  # melodic grace note. Must be followed by a melodic note.
        r"X(?=x)|Y(?=y)|K(?=k)|B(?=b)",  # non-melodic grace note. Must be followed by a note with the same pitch.
        r"[\-\.][_=]{0,1}",  # rest optionally followed by note duration modifier and grace note
        r"[GPTX]",  # gong section (GPT) without modifier
    ]
    GRACE_NOTES = "AEIOU"

    # List of characters that change the octave, stroke or duration of the preceding note
    MODIFIERS_PATTERN = "[,<:;_=/?]+[AEIOU]{0,1}"

    def __init__(self, run_settings: RunSettings):
        super().__init__(self.ParserType.NOTATIONPARSER, run_settings)
        self.run_settings = run_settings
        with open(run_settings.notation.filepath, "r") as input:
            self.notation_lines = [line.rstrip() for line in input]

    def _sort_modifiers(self, notes: str) -> str:
        """Sorts the modifier characters to simplify the validation

        Args:
            notes (str): list of characters

        Returns:
            str: the string, with modifier characters ordered
        """
        offset = 0
        # Search the string for groups of modifiers
        while offset < len(notes) and (match := re.search(self.MODIFIERS_PATTERN, notes[offset:])):
            matchstart = offset + match.start()
            matchend = offset + match.end()
            # The `sorted` function converts the string into a list of characters, hence the `join` operation.
            sorted_modifiers = "".join(sorted(notes[matchstart:matchend], key=lambda x: self.MODIFIERS_PATTERN.find(x)))
            notes = notes[:matchstart] + sorted_modifiers + notes[matchend:]
            offset = matchend + 1
        return notes

    def _note_from_chars(self, position: Position, note_chars: tuple[str]) -> list[Note]:
        """Translates a list of characters to a Note object.

        Args:
            position (Position): _description_
            note_chars (str): A set of characters consisting of a note followed by modifier characters.
            prev_note (Note): preceding note, which has already been parsed (the note might occur in another beat).
            next_note_chars (str): following note, not yet parsed. Is needed to process some modifiers.

        Returns:
            Note: a list containing one or two notes.
        """
        # Create a list containing one Note object for each symbol in note_chars.
        notes = []
        char_groups = [group for group in note_chars if group]
        for chars in char_groups:
            if note := LOOKUP.POSITION_CHARS_TO_NOTELIST.get((position, chars), None):
                notes.append(note)
            else:
                self.logerror(f"Illegal character(s) {chars} for {position}")

        if notes and all(note.stroke in (Stroke.TREMOLO, Stroke.TREMOLO_ACCELERATING) for note in notes):
            notes = self._generate_tremolo(notes)

        return notes

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

    def _parse_stave(self, stave: str, position: Position) -> list[Note]:
        """Validates the notation

        Args:
            stave (str): one stave of notation
            position (Position):

        Returns: str | None: _description_
        """
        # Sort the modifiers so that they will always appear in the same order.
        # This reduces the number of necessary validation patterns.
        note_chars = self._sort_modifiers(stave)

        notes = []  # will contain the Note objects
        # Group each note character with its corresponding modifier characters
        while note_chars:
            for pattern in self.NOTATION_PATTERNS:
                match = re.match(pattern, note_chars)
                if match:
                    break
            if not match:
                self.logerror(f" {position.value} {stave} has invalid {note_chars[0]}")
                note_chars = note_chars[1:]
            else:
                note = self._note_from_chars(
                    position=position,
                    # If the pattern has capturing groups,
                    note_chars=[group for group in match.groups() if group] or [match.group(0)],
                )
                notes.extend(note)
                note_chars = note_chars[match.end() :]

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
            self.logerror(str(err).replace("\n", "."))
            return None

        return metadata

    def _replace_grace_notes(self, line: str) -> str:
        """Replaces the inaccurate grace note notation with an accurate equivalent.
        A grace note represents a short off-beat note before the next note. The interpretation is that
        a grace note combines with the previous note or rest by replacing part of the duration
        of that previous note or rest. W

        Grace cause two complications:
        1. A grace note is both a note and a modifier: it affects the duration of the preceding note.
        2. A grace note is accepted at the beginning of a beat. This is inaccurate because the grace note
            actually belongs to the preceding beat.
        Both problems are tackled by replacing the grace note

        Args:
            line (str): _description_

        Returns:
            str: _description_
        """

        def replace(m: re.Match):
            # TODO This only works if the previous note is not a half or quarter note. This is not checked.
            return f"{m.group(1)}_{m.group(3).lower()}_{m.group(2)}"

        if len(line) <= 1:
            # No notation: nothing to do
            return line
        notation_part = "\t".join(line[1:])
        notation_part = re.sub(r"(.)(\t{0,1})([" + self.GRACE_NOTES + "])", replace, notation_part)
        return line[:1] + notation_part.split("\t")

    def _get_nearest_octave(self, note: Note, other_note: Note, noterange: list[tuple[Pitch, Octave]]) -> Octave:
        """Returns the octave for note that minimizes the distance between the two note pitches.

        Args:
            note (Note): note for which to optimize the octave
            other_note (Note): reference nte
            noterange (list[tuple[Pitch, Octave]]): available note range

        Returns:
            Octave: the octave that puts the pitch of note nearest to that of other_note
        """
        next_note_idx = noterange.index((other_note.pitch, other_note.octave))
        octave = None
        best_distance = 99
        for offset in [0, 1, -1]:
            new_octave = other_note.octave + offset
            if (note.pitch, new_octave) in noterange and (
                new_distance := abs(noterange.index((note.pitch, new_octave)) - next_note_idx)
            ) < best_distance:
                octave = new_octave
                best_distance = min(new_distance, best_distance)
        return octave

    def _generate_tremolo(self, notes: list[Note]) -> list[Note]:
        """Generates the note sequence for a tremolo.
         TREMOLO: The duration and pitch will be that of the given note.
         TREMOLO_ACCELERATING: The pitch will be that of the given note, the duration will be derived
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
                tremolo_notes.append(note.model_copy(update={"duration": duration, "_validate_range": False}))
        elif notes[0].stroke is Stroke.TREMOLO_ACCELERATING:
            durations = [i / BASE_NOTE_TIME for i in self.TREMOLO_ACCELERATING_PATTERN]
            note_idx = 0
            for duration, velocity in zip(durations, self.TREMOLO_ACCELERATING_VELOCITY):
                tremolo_notes.append(
                    notes[note_idx].model_copy(
                        update={"duration": duration, "velocity": velocity, "_validate_range": False}
                    )
                )
                note_idx = (note_idx + 1) % len(notes)
        else:
            self.logerror(f"Unexpected tremolo type {notes[0].stroke}.")

        return tremolo_notes

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

        for line_nr, line in enumerate(self.notation_lines):
            # remove trailing tabs and split the line on the remaining tabs.
            line = re.sub(r"\t+$", "", line).split("\t")

            tag = line[0]
            # Skip empty lines
            match tag:
                case "":
                    if len(line) > 1:
                        self.logerror(f"line {line_nr} has content but has no label in the first position.")
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
                        if not LOOKUP.TAG_TO_POSITION.get(pos, None):
                            self.logerror(f"unrecognized instrument tag {pos}.")
                            continue
                        # Grace note is an inaccurate shorthand notation: replace with exact notation.
                        line = self._replace_grace_notes(line)
                        positions = [Position[tag] for tag in LOOKUP.TAG_TO_POSITION.get(pos, [])]
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

        if self.has_errors:
            self.logger.error("Program halted.")
            exit()

        notation = Notation(notation_dict=notation_dict, settings=self.run_settings)

        return notation


# ==================== GENERAL CODE =====================================


def get_parser(run_settings: RunSettings):
    if run_settings.font.fontversion is NotationFont.BALIMUSIC5:
        return Font5Parser(run_settings)
    else:
        raise NotImplementedError(f"No parser available for font {run_settings.font.fontversion}.")


if __name__ == "__main__":
    run_settings = get_run_settings()
    parser = Font5Parser(run_settings)
    line = r"u_,"
    print(f"{line} ==> {parser._sort_modifiers(line)}")
