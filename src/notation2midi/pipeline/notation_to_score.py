"""Creates a midi file based on a notation file.
See ./data/README.md for more information about notation files and ./data/notation/test
for an example of a notation file.
Main method: convert_notation_to_midi()
"""

import copy
from collections import defaultdict
from dataclasses import _MISSING_TYPE, asdict
from typing import override

from src.common.classes import Beat, Gongan, Measure, Notation, Score
from src.common.constants import (  # RuleType,
    DEFAULT,
    NotationDict,
    ParserTag,
    Position,
    VelocityInt,
)
from src.common.notes import NoteFactory

# from src.common.rules import RulesEngine
from src.notation2midi.classes import Agent, MetaDataRecord, NamedIntID
from src.notation2midi.metadata_classes import (
    CopyMeta,
    MetaData,
    MetaDataAdapter,
    MetaType,
)
from src.settings.classes import RunSettings

# pylint incorrectly reports an error when Pydantic fields are pre-assigned with the Field function
# pylint disable = no - member


class BeatID(NamedIntID):
    name = "BEAT"


class ScoreCreatorAgent(Agent):
    """Parser that converts the results of the notation parser into a Score object.
    This parser uses 'knowledge' about the instruments and idiom of the music to interpret the notation.
    It also processes the metadata.
    """

    LOGGING_MESSAGE = "CONVERTING NOTATION DICT TO SCORE"
    EXPECTED_INPUT_TYPES = (Agent.InputOutputType.RUNSETTINGS, Agent.InputOutputType.NOTATION)
    RETURN_TYPE = Agent.InputOutputType.GENERICSCORE

    notation: Notation = None
    score: Score = None

    POSITIONS_EXPAND_MEASURES = [
        Position.UGAL,
        Position.CALUNG,
        Position.JEGOGAN,
        Position.GONGS,
        Position.KEMPLI,
    ]

    default_velocity: VelocityInt

    def __init__(self, run_settings: RunSettings, notation: Notation):
        super().__init__(run_settings)
        self.notation = notation
        self.default_velocity = self.run_settings.midi.dynamics[self.run_settings.midi.default_dynamics]

        self.score = Score(
            title=self.run_settings.notation_settings.title,
            settings=notation.settings,
            instrument_positions=self._get_all_positions(notation.notation_dict),
        )

    @override
    @classmethod
    def run_condition_satisfied(cls, run_settings: RunSettings):
        return True

    def _get_all_positions(self, notation_dict: NotationDict) -> set[Position]:
        all_instruments = [
            stave[ParserTag.POSITION]
            for gongan_id, gongan in notation_dict.items()
            if gongan_id > 0
            for stave in gongan[ParserTag.STAVES]
        ]
        return set(all_instruments)

    def _staves_to_beats(self, staves: list[dict]) -> list[dict]:
        """Tranforms the staves -> measures hierarchy of the notation_dict to beats -> measures.
            target structure is: gongan[beat_id][position][passes]
        Args:
            staves (list[dict]): staves belonging to the same gongan.

        Returns:
            list[dict]: the transposed structure
        """
        if not staves:
            return {}
        # There can be multiple staves with the same `position` value. In that case they will have different `pass`
        # values. The staves first need to be grouped by position. We create a position dict for this, will also
        # be used below to retrieve the correct ALL_POSITIONS value when a new Measure is created.
        position_dict = {stave[ParserTag.POSITION]: stave[ParserTag.ALL_POSITIONS] for stave in staves}
        staves_by_pos_pass = {
            position: {int(stave[ParserTag.PASS]): stave for stave in staves if stave[ParserTag.POSITION] == position}
            for position in position_dict.keys()
        }
        # count only non-empty beats
        beat_count = max(len([measure for measure in stave[ParserTag.MEASURES] if measure]) for stave in staves)
        beats = {
            BeatID(beat_seq + 1): {
                position: Measure(
                    position=position,
                    all_positions=position_dict[position],  # positions,
                    passes={
                        stave[ParserTag.PASS]: (
                            Measure.Pass(
                                seq=stave[ParserTag.PASS],
                                line=stave[ParserTag.LINE],
                                notesymbols=(
                                    stave[ParserTag.MEASURES][beat_seq]
                                    if beat_seq < len(stave[ParserTag.MEASURES])
                                    else []
                                ),
                            )
                        )
                        for pass_, stave in position_staves.items()
                    },
                )
                for position, position_staves in staves_by_pos_pass.items()
            }
            for beat_seq in range(beat_count)
        }

        return beats

    def _record_to_metadata(self, record_list: list[MetaDataRecord]) -> defaultdict[MetaType, list[MetaData]]:
        """Converts a list of MetaDataRecord objects into a list of MetaData objects."""
        metadata_dict = defaultdict(list)
        if not record_list:
            return metadata_dict
        for record in record_list:
            self.curr_line_nr = record.line
            metadata: MetaData = MetaDataAdapter.validate_python(
                {key: val for key, val in asdict(record).items() if not isinstance(val, _MISSING_TYPE)}
            )
            metadata_dict[metadata.metatype].append(metadata)
        return metadata_dict

    def apply_template(self, gongan: dict[ParserTag, dict[int, dict[Position, Measure]]], copymeta: CopyMeta):
        """Merges the given beats dict with a copy of the beats dict of the template beat given by copymeta"""
        # Look up the template in the score in order to determine its ID.
        template_gongan = next(
            (g for g in self.score.gongans if any(lbl.name == copymeta.template for lbl in g.metadata[MetaType.LABEL])),
            None,
        )
        if not template_gongan:
            raise ValueError(
                "Template '%s' is missing for COPY reference. The template should be defined before the COPY statement."
            )
        template_copy = copy.deepcopy(self.notation.notation_dict[template_gongan.id][ParserTag.BEATS])
        if not gongan[ParserTag.BEATS]:
            # Assign the template's beats to the gongan
            gongan[ParserTag.BEATS] = template_copy
        elif len(template_copy) != len(gongan[ParserTag.BEATS]):
            raise ValueError(
                "COPY statement: the number of beats does not match that of template '%s'." % copymeta.template
            )
        else:
            # Update the template's beats with the gongan's beats and assign the result to the gongan.
            # (i.e. perform merge gongan -> template)
            for beat_id in template_copy:
                gongan[ParserTag.BEATS][beat_id] = template_copy[beat_id] | gongan[ParserTag.BEATS][beat_id]
        if copymeta.include:
            # Add the requested template's metadata to the gongan
            for tag in copymeta.include:
                gongan[ParserTag.METADATA][tag] += template_gongan.metadata[tag]

    def update_line_nr(self):
        line_nr = 0

        if self.curr_gongan_id:
            gongan = self.notation.notation_dict[self.curr_gongan_id]
            if self.curr_beat_id:
                if self.curr_position:
                    line_nr = gongan[ParserTag.BEATS][self.curr_beat_id][self.curr_position].passes[DEFAULT].line
                else:
                    if gongan[ParserTag.BEATS][self.curr_beat_id]:
                        line_nr = list(gongan[ParserTag.BEATS][self.curr_beat_id].values())[0].line
            else:
                if gongan[ParserTag.METADATA]:
                    line_nr = gongan[ParserTag.METADATA][0].line
                elif ParserTag.BEATS in gongan and gongan[ParserTag.BEATS] and gongan[ParserTag.BEATS][0]:
                    line_nr = list(gongan[ParserTag.BEATS][0].values())[0].line
        self.curr_line_nr = line_nr

    def _create_score_object_model(self) -> Score:
        """Creates an object model of the notation. The method aggregates each note and the corresponding diacritics
        into a single note object, which will simplify the generation of the MIDI file content.

        Args:
            datapath (str): path to the data folder
            infilename (str): name of the csv input file
            title (str): Title for the notation

        Returns:
            Score: A Score object model, not yet validated for inconsistencies.
        """

        beats: list[Beat] = []
        measures: dict[Position, Measure]
        for self.curr_gongan_id, gongan_info in self.notation.notation_dict.items():
            self.reset_counters(Agent.IteratorLevel.BEAT)
            self.update_line_nr()
            # Transpose the gongan from stave-oriented to beat-oriented
            gongan_info[ParserTag.BEATS] = self._staves_to_beats(gongan_info[ParserTag.STAVES])
            del gongan_info[ParserTag.STAVES]
            # Convert the metadata records to MetaData instances
            try:
                metadata_dict: dict[MetaType, list[MetaData]] = self._record_to_metadata(
                    gongan_info.get(ParserTag.METADATA, [])
                )
            except ValueError as err:
                self.logerror(str(err))
            gongan_info[ParserTag.METADATA] = metadata_dict

            if self.curr_gongan_id == DEFAULT:
                # Store global metadata and comment. Global gongan does not contain notation.
                self.score.global_metadata = metadata_dict
                self.score.global_comments = gongan_info.get(ParserTag.COMMENTS, [])

            # in case of a COPY metadata, merge the template gongan data into this gongan data
            if gongan_info[ParserTag.METADATA][MetaType.COPY]:
                try:
                    self.apply_template(gongan_info, gongan_info[ParserTag.METADATA][MetaType.COPY][0])
                except ValueError as err:
                    print(self.curr_gongan_id)
                    self.logerror(str(err))

            for self.curr_beat_id, measures in gongan_info[ParserTag.BEATS].items():
                # Generate measure content: convert NoteRecord objects to NoteSymbol objects.
                for self.curr_position, measure in measures.items():
                    self.update_line_nr()
                    for _, pass_ in measure.passes.items():
                        self.curr_line_nr = pass_.line
                        try:
                            pass_.genericnotes = [
                                NoteFactory.genericnote_from_notesymbol(notechars) for notechars in pass_.notesymbols
                            ]
                        except ValueError as err:
                            self.logerror(str(err))

                # Create the beat and add it to the list of beats
                new_beat = Beat(
                    id=int(self.curr_beat_id),
                    gongan_id=int(self.curr_gongan_id),
                    measures=measures,
                )

                prev_beat = beats[-1] if beats else self.score.gongans[-1].beats[-1] if self.score.gongans else None
                # Update the `next` pointer of the previous beat.
                if prev_beat:
                    prev_beat.next = new_beat
                    new_beat.prev = prev_beat
                beats.append(new_beat)

            # Create a new gongan
            if beats or self.curr_gongan_id != DEFAULT:
                metadata = gongan_info.get(ParserTag.METADATA, {})
                gongan = Gongan(
                    id=int(self.curr_gongan_id),
                    beats=beats,
                    metadata=metadata,
                    comments=gongan_info.get(ParserTag.COMMENTS, defaultdict()),
                )
                self.score.gongans.append(gongan)  # pylint: disable=no-member
                beats = []

    def _add_global_metadata_to_each_gongan(self) -> None:
        # update each gongan with the score's global metadata
        for gongan in self.gongan_iterator(self.score):
            for metatype, global_meta in self.score.global_metadata.items():
                gongan.metadata[metatype] += global_meta

    def _main(self):
        """This method does all the work.
        All settings are read from the (YAML) settings files.
        """

        self._create_score_object_model()
        self._add_global_metadata_to_each_gongan()
        self.abort_if_errors()

        return self.score


if __name__ == "__main__":
    pass
