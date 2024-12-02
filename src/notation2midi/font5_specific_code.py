import re
from collections import defaultdict

from src.common.classes import FontParser, Note
from src.common.constants import (
    DEFAULT,
    Duration,
    InstrumentPosition,
    Modifier,
    NotationDict,
    NotationFont,
    Octave,
    Pitch,
    SpecialTags,
    Stroke,
)
from src.common.lookups import MIDINOTE_LOOKUP, TAG_TO_POSITION_LOOKUP
from src.common.metadata_classes import MetaData, MetaDataSubType
from src.common.utils import NOTE_LIST, flatten, get_instrument_range, get_nearest_note
from src.settings.settings import BASE_NOTE_TIME

# ==================== BALI MUSIC 5 FONT =====================================


class Font5Parser(FontParser):

    TREMOLO_NR_OF_NOTES_PER_QUARTERNOTE: int = 3  # should be a divisor of BASE_NOTE_TIME
    # Next values are in 1/BASE_NOTE_TIME. E.g. if BASE_NOTE_TIME=24, then 24 is a standard note duration.
    # Should also be an even number so that alternating note patterns end on the second note.
    TREMOLO_ACCELERATING_PATTERN: list[int] = [48, 40, 32, 26, 22, 18, 14, 10, 10, 10, 10, 10]
    TREMOLO_ACCELERATING_VELOCITY: list[int] = [100] * (len(TREMOLO_ACCELERATING_PATTERN) - 5) + [90, 80, 70, 60, 50]

    NOTATION_PATTERNS = [
        r"([aeiourskxytb089\(\)\*][,<]{0,1}[:;]){1,2}",  # one or two occurrences of a melodic note followed by an optional octave and a tremolo symbols.
        r"[kxytb089\(\)\*][:;]",  # non-melodic note followed by a tremolo symbol.
        r"[aeiours][,<]{0,1}[_=]{0,1}[/?]{0,1}",  # melodic note symbol optionally followed by octave symbol, note duration modifier and/or mute/abbrev symbol
        r"[kxytb][_=]{0,1}[/?]{0,1}",  # non-melodic symbol optionally followed by note duration modifier and/or mute/abbrev symbol
        r"[AEIOU](?=[aeiou])",  # melodic grace note. Must be followed by a melodic note.
        r"X(?=x)|Y(?=y)|K(?=k)|B(?=b)",  # non-melodic grace note. Must be followed by a note with the same pitch.
        r"[\-\.][_=]{0,1}",  # rest optionally followed by note duration modifier and grace note
        r"[GPTX089\(\)\*]",  # gong section (GPT) or kendang stroke without modifier
    ]
    # List of characters that change the octave, stroke or duration of the preceding note
    MODIFIERS_PATTERN = "[,<:;_=/?]+[AEIOU]{0,1}"

    def sort_modifiers(self, notes: str) -> str:
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

    def note_from_chars(self, position: InstrumentPosition, note_chars: str) -> list[Note]:
        """Translates a list of characters to a Note object (or two in case one of the characters is a grace note).
        The note's postprocess flags is set if not all its parameter values can be determined in this step.

        Args:
            position (InstrumentPosition): _description_
            note_chars (str): A set of characters consisting of a note followed by modifier characters.
            prev_note (Note): preceding note, which has already been parsed (the note might occur in another beat).
            next_note_chars (str): following note, not yet parsed. Is needed to process some modifiers.

        Returns:
            Note: a list containing one or two notes.
        """
        notes: list[Note] = [
            next((note for note in NOTE_LIST if (note.symbol == character)), None) for character in note_chars
        ]

        if len(notes) == 1:
            return notes

        # notes list contains modifiers.

        note = notes.pop(0)  # The actual note. Any other 'note' is a modifier.
        note_chars = note.symbol
        modifs = dict()  # Keeps track of modifications that should be applied to the note.

        # Check required actions
        while notes:
            modifier_note = notes.pop(0)
            note_chars += modifier_note.symbol
            match modifier_note.modifier:
                case Modifier.OCTAVE_0:
                    modifs["octave"] = 0
                case Modifier.OCTAVE_2:
                    modifs["octave"] = 2
                case Modifier.MUTE | Modifier.ABBREVIATE:
                    if (position, note.pitch, 1, note.stroke) in MIDINOTE_LOOKUP:
                        # Midi entry found: keep previous note durations and change its stroke type
                        modifs["stroke"] = modifier_note.stroke
                    else:
                        # No separate MIDI entry: emulate the stroke by modifying the note duration
                        modifs["duration"], modifs["rest_after"] = self.apply_ratio(note, modifier_note)
                case Modifier.HALF_NOTE | Modifier.QUARTER_NOTE:
                    modifs["duration"] = modifs.get("duration", note.duration) * modifier_note.duration
                    modifs["rest_after"] = modifs.get("rest_after", note.rest_after) * modifier_note.rest_after
                case Modifier.GRACE_NOTE:  # move to post-process. This case will never be encountered here.
                    # Subtract the duration of the grace note from its predecessor.
                    # A grace note cannot be followed by a modifier so at this stage we know the final duration of the note.
                    duration, rest_after = modifs.get("duration", note.duration), modifs.get(
                        "rest_after", note.duration
                    )
                    rest_after = modifs["rest_after"] = max(0, rest_after - modifier_note.duration)
                    duration = modifs["duration"] = max(0, duration - (modifier_note.duration - rest_after))
                    # A grace note is both a modifier and a note in itself. However the modified note might be stored in the previous
                    # beat. Furthermore the octave of the grace note should be derived from the note following it.
                    # These operations cannot be performed here and will take place in a separate postprocessing step.
                case Modifier.TREMOLO:
                    if notes:
                        modifs["stroke"] = Modifier.TREMOLO
                case Modifier.TREMOLO_ACCELERATING:
                    # An accelarating tremolo modifier can be followed by a second note + tremolo modifier combination.
                    # The patterns in NOTATION_PATTERNS ensure that no other character combination can follow.
                    if notes:
                        # Expecting another tremolo definition. Store the current note and create a new note.
                        modifs["stroke"] = Modifier.TREMOLO
                        modifs["symbol"] = note_chars
                        notes.append()
                        note = notes.pop(0)
                        modifs = dict()
                        note_chars = note.symbol

        modifs["symbol"] = note_chars
        notes.append(note.model_copy(update=modifs))

        # Generate tremolo. Grace note will be created in a separate postprocessing step.
        if all(note.modifier in [Modifier.TREMOLO, Modifier.TREMOLO_ACCELERATING] for note in notes):
            notes = self.generate_tremolo(notes)

        return notes

    def postprocess_note(
        self, current: Note, previous: Note, next_: Note, instrument_range: list[tuple[Pitch, Octave]]
    ) -> tuple[list[Note]]:
        """Performs modifications that need information about surrounding notes (currently only needed for grace notes)

        Args:
            current (Note): the note that should be treated
            previous (Note | None): predecessor of the note
            next_ (Note | None): the successor of the note
            instrument_range (list[tuple[Pitch, Octave]]): _description_

        Returns:
            tuple[Note]: _description_
        """
        if current.modifier is not Modifier.GRACE_NOTE:
            return [], []
        # A grace note is both a note and a modifyer.
        # 1. Subtract its length from the preceding note.
        # 2. Determine its octave (grace notes can't be combined with an octave indicator).
        if next_ and current.octave:
            octave = self.get_nearest_octave(current, next_, instrument_range)
        else:
            octave = current.octave

        # Subtract the duration of the grace note from its predecessor
        new_rest_after = max(0, previous.rest_after - current.duration)
        new_duration = max(0, previous.duration - (current.duration - new_rest_after))
        new_prev = previous.model_copy(update={"duration": new_duration, "rest_after": new_rest_after})
        # Add the grace note with the correct octave
        new_curr = current.model_copy(update={"octave": octave})

        return [new_prev, new_curr], []

    def parse_stave(self, stave: str, position: InstrumentPosition) -> list[Note]:
        """Validates the notation

        Args:
            stave (str): one stave of notation
            position (InstrumentPosition):

        Returns: str | None: _description_
        """
        # Sort the modifiers so that they will always appear in the same order.
        # This reduces the number of necessary validation patterns.
        note_chars = self.sort_modifiers(stave)

        notes = []  # will contain the Note objects
        # Group each note character with its corresponding modifier characters
        while note_chars:
            for pattern in self.NOTATION_PATTERNS:
                match = re.match(pattern, note_chars)
                if match:
                    break
            if not match:
                self.log_error(f" {position.value} `{stave}` has invalid `{note_chars[0]}`")
                note_chars = note_chars[1:]
            else:
                note = self.note_from_chars(position=position, note_chars=match.group(0))
                notes.extend(note)
                note_chars = note_chars[match.end() :]

        return notes

    def parse_special_tag(self, tag: SpecialTags, content: str) -> list[str | MetaData]:
        # Create a dict {KEYWORD: {parameter: typing | class}} that contains valid MetaData tag content
        METADATA_TYPE_DICT = {
            meta.__annotations__["metatype"].__args__[0]: {
                attr: str(cls) for attr, cls in meta.__annotations__.items() if attr != "metatype"
            }
            for meta in MetaDataSubType.__args__
        }

        # Check the tag. Return comments without further processing.
        match tag:
            case SpecialTags.COMMENT:
                return content, set()
            case SpecialTags.METADATA:
                pass
            case _:
                return {"Unrecognized tag {tag}"}

        # Check metadata values
        metadata = None

        # Validate the general format of the metadata content (value between braces, starting with keyword)
        match = re.match(r"\{(?P<keyword>[A-Z]+) +(.*)}$", content.strip())
        if not match:
            self.log_error(
                f"metadata {content} is not formatted correctly. "
                "Check that the value starts with a keyword in capitals and is enclosed in braces."
            )
            return None

        # Check if the metadata keyword is valid
        keyword = match["keyword"]
        if keyword not in METADATA_TYPE_DICT.keys():
            possibe_keywords = list(METADATA_TYPE_DICT.keys())
            self.log_error(f"incorrect metadata keyword `{keyword}`. Possible values are {possibe_keywords}")
            return None

        # Try to parse the string value
        try:
            metadata = MetaData(data=content)
        except:
            possibe_parameters = list(METADATA_TYPE_DICT[keyword].keys())
            self.log_error(
                f"invalid metadata format {content}. Check the syntax. Possible parameters: {possibe_parameters}."
            )
            return None

        return metadata

    def parse_notation(self) -> tuple[NotationDict, list[InstrumentPosition]]:
        """Parses a notation file into a dict.

        Args:
            filepath (str): Path to the notation file.

        Returns:
            NotationDict: A dict notation[gongan_id][beat_id][position][passes] that can be processed into a Score object.
        """
        notation_dict = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
        new_system = True
        self.curr_gongan_id = 0
        all_positions = set()
        prev_staves = defaultdict(list)

        for line_nr, line in enumerate(self.notation_lines):
            # remove trailing tabs and split the line on the remaining tabs.
            line = re.sub(r"\t+$", "", line).split("\t")

            tag = line[0]
            # Skip empty lines
            match tag:
                case "":
                    if len(line) > 1:
                        self.log_error(f"line {line_nr} has content but has no label in the first position.")
                    new_system = True
                    continue
                case _:
                    if new_system:
                        self.curr_gongan_id += 1
                        # Metadata and comments are stored on gongan level
                        notation_dict[self.curr_gongan_id][SpecialTags.METADATA] = []
                        notation_dict[self.curr_gongan_id][SpecialTags.COMMENT] = []
                        new_system = False

            # Process metadata and notation
            match tag:
                case SpecialTags.METADATA | SpecialTags.COMMENT:
                    parsed = self.parse_special_tag(tag, content=line[1])
                    notation_dict[self.curr_gongan_id][tag].append(parsed)
                    continue
                case _:
                    # Process notation data
                    if len(line) > 1:
                        if not TAG_TO_POSITION_LOOKUP.get(tag, None):
                            self.log_error(f"unrecognized instrument tag {tag}.")
                            continue
                        positions = [InstrumentPosition[tag] for tag in TAG_TO_POSITION_LOOKUP.get(tag, [])]
                        all_positions = all_positions | set(positions)
                        for self.curr_beat_id in range(1, len(line)):
                            for self.curr_position in positions:
                                instrument_range = get_instrument_range(self.curr_position)
                                if line[self.curr_beat_id]:
                                    curr_stave = self.parse_stave(
                                        stave=line[self.curr_beat_id], position=self.curr_position
                                    )
                                    # Postprocess notes. This performs operations where information about surrounding notes is needed.
                                    if len(curr_stave) > 0:
                                        prev_stave = prev_staves[self.curr_position]  # stave containing the 'prev' note
                                        # Create an extended range containing surrounding notes for each note of the stave
                                        curr_stave_ext = (
                                            [([None] + prev_staves[self.curr_position])[-1]] + curr_stave + [None]
                                        )
                                        for i in range(0, len(curr_stave)):
                                            # Be aware that prev and curr are lists of Note objects.
                                            prev, curr = self.postprocess_note(
                                                previous=curr_stave_ext[i],
                                                current=curr_stave_ext[i + 1],
                                                next_=curr_stave_ext[i + 2],
                                                instrument_range=instrument_range,
                                            )
                                            # We store prev and curr as list objects to keep the number of objects in curr_stave constant.
                                            # After the loop is finished, we will unpack any list that was added to the staves.
                                            if prev or curr:
                                                prev_stave[i - 1] = prev
                                                curr_stave[i] = curr
                                            prev_stave = curr_stave  # the 'prev' note will occur in the current stave for the next iterations
                                        # Now unpack the lists of notes in the staves
                                        flatten(prev_staves[self.curr_position])
                                        flatten(curr_stave)

                                    notation_dict[self.curr_gongan_id][self.curr_beat_id][self.curr_position][
                                        DEFAULT
                                    ] = curr_stave
                                    prev_staves[self.curr_position] = notation_dict[self.curr_gongan_id][
                                        self.curr_beat_id
                                    ][self.curr_position][
                                        DEFAULT
                                    ]  # curr_stave becomes the new prev_stave
                                else:
                                    # Create an empty beat. This  ensures a correct ordering of the beats.
                                    # (notation_dict is a defaultdict)
                                    notation_dict[self.curr_gongan_id][self.curr_beat_id]

        all_positions = sorted(list(all_positions), key=lambda p: p.sequence)

        if self._has_errors:
            notation_dict = None

        return notation_dict, all_positions

    def apply_ratio(self, note: Note, ratio_note: Note) -> tuple[Duration, Duration]:
        total_duration = note.total_duration
        new_duration = total_duration * ratio_note.duration
        new_time_after = total_duration - new_duration
        return new_duration, new_time_after

    def get_nearest_octave(self, note: Note, other_note: Note, noterange: list[tuple[Pitch, Octave]]) -> Octave:
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

    def remove_from_last_note_to_end(stave: list[Note]) -> tuple[Note | None, list[Note]]:
        """Searches for the last note in stave and removes this note and all notes following it.

        Args:
            stave (list[Note]): list to be searched.

        Returns:
            tuple[Note | None, list[Note]]: The last note if found and the notes following it.
        """
        modifiers = []
        note = None
        while stave and not note:
            element = stave.pop(-1)
            if element.pitch is not Pitch.NONE:
                note = element
            else:
                modifiers.append(element)
        return note, modifiers

    def generate_tremolo(self, notes: list[Note]) -> list[Note]:
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

        if notes[0].modifier is Modifier.TREMOLO:
            note = notes[0]
            nr_of_notes = round(note.duration * self.TREMOLO_NR_OF_NOTES_PER_QUARTERNOTE)
            duration = note.duration / nr_of_notes
            for _ in range(nr_of_notes):
                tremolo_notes.append(note.model_copy(update={"duration": duration}))
        elif notes[0].modifier is Modifier.TREMOLO_ACCELERATING:
            durations = [i / BASE_NOTE_TIME for i in self.TREMOLO_ACCELERATING_PATTERN]
            note_idx = 0
            for duration, velocity in zip(durations, self.TREMOLO_ACCELERATING_VELOCITY):
                tremolo_notes.append(notes[note_idx].model_copy(update={"duration": duration, "velocity": velocity}))
                note_idx = (note_idx + 1) % len(notes)
        else:
            self.log_error(f"Unexpected tremolo type {notes[0].modifier}.")

        return tremolo_notes

    def create_note(
        self,
        pitch: Pitch,
        octave: Octave,
        stroke: Stroke,
        duration: Duration,
        rest_after: Duration = None,
        symbol: str = None,
        font: NotationFont = NotationFont.BALIMUSIC5,
    ) -> Note:
        """Returns the first note with the given characteristics

        Args:
            pitch (Pitch): _description_
            octave (Octave): _description_
            stroke (Stroke): _description_
            duration (Duration): _description_
            rest_after (Duration): _description_
            symbol (str): _description_
            font(NotationFont): the font used

        Returns:
            Note: a copy of a Note from the note list if a match is found, otherwise an newly created Note object.
        """
        note = get_nearest_note(pitch, stroke, duration, rest_after, octave, NOTE_LIST)
        # TODO error handling if note == None
        note_symbol = note.symbol

        # With BALIMUSIC5 font, symbol can consist of more than one character: a pitch symbol followed by one or more modifier symbols
        additional_symbol = ""
        symbol = note_symbol
        if symbol[0] in "1234567" and note_symbol in "ioeruas":
            # replace regular pitch symbol with grace note equivalent
            note_symbol = "1234567"["ioeruas".find(note_symbol)]
        additional_symbol = "," if octave == 0 else "<" if octave == 2 else ""
        additional_symbol += "/" if stroke == Stroke.ABBREVIATED else "?" if stroke == Stroke.MUTED else ""

        return note.model_copy(
            update={
                "symbol": note_symbol + additional_symbol + symbol[1:],
                "octave": octave if octave else note.octave,
                "stroke": stroke if stroke else note.stroke,
                "duration": duration if duration else note.duration,
                "rest_after": rest_after if rest_after else note.rest_after,
            }
        )


# ==================== GENERAL CODE =====================================


def get_parser(font: NotationFont, filepath: str):
    if font is NotationFont.BALIMUSIC5:
        return Font5Parser(filepath)
    else:
        raise NotImplementedError(f"No parser available for font {font.value}.")


if __name__ == "__main__":
    pass
