"""This is the module that actually generates the JSON structure.
It is used by the score_to_json module.
"""

import json
from collections import defaultdict
from typing import cast
from uuid import uuid4

from src.common.classes import Gongan
from src.common.classes import Score as PythonScore
from src.common.constants import DynamicLevel, Position
from src.common.logger import Logging
from src.notationparser.json.compact_encoder import CompactEncoder
from src.notationparser.json.tooltip import executionItemTooltip
from src.notationparser.json.types import (
    DynamicsItem,
    ExecutionItemBase,
    GotoItem,
    LoopItem,
    Measure,
    Score,
    System,
    TempoItem,
)
from src.notationparser.metadata_classes import (
    DynamicsMeta,
    MetaDataType,
    MetaType,
    PartMeta,
    TempoMeta,
)
from src.settings.classes import RunSettings

logger = Logging.get_logger(__name__)


class JsonCreator:
    """
    Converts a Score object to JSON notation.
    """

    SUSTAIN_DURATION: int = 20

    def __init__(self, pscore: PythonScore, run_settings: RunSettings):
        super().__init__()
        self.run_settings = run_settings
        self.positions = pscore.instrument_positions
        self.score = Score(
            uuid=str(uuid4()),
            title=pscore.title,
            composer=pscore.composer,
            instrumenttype=self.run_settings.instrumentgroup,
            # pylint: disable=protected-access
            # pylint: disable=no-member
            positions=sorted(self.positions, key=Position._member_names_.index),
            parts=defaultdict(list),
        )
        self.current_part = None
        (self.uuiddict, self.labeldict) = self.createSectionUuids(pscore)

    # Creates a dict with a uuid for each section, and a lookup dict label -> uuid
    def createSectionUuids(self, pscore: PythonScore):
        uuiddict = {gongan.id: str(uuid4()) for gongan in pscore.gongans}
        gotolabels = set([goto.label for gongan in pscore.gongans for goto in gongan.metadata[MetaType.GOTO]])
        # Only keep labels that are used for Goto metadata. This will omit labels used for Copy metadata.
        labeldict = {
            gongan.metadata[MetaType.LABEL][0].name: uuiddict[gongan.id]
            for gongan in pscore.gongans
            if gongan.metadata[MetaType.LABEL] and gongan.metadata[MetaType.LABEL][0].name in gotolabels
        }
        return (uuiddict, labeldict)

    def velocity2frac(self, velocity: int) -> float:
        return round(velocity / 127, 2)

    def get_execution(self, metadata: dict[MetaType, list[MetaDataType]]) -> list[ExecutionItemBase]:
        execution = []
        seqId = 0
        if metadata[MetaType.GOTO]:
            for item in metadata[MetaType.GOTO]:
                newitem = GotoItem(
                    type="goto",
                    seqId=seqId,
                    passes=item.passes or None,
                    nthpass=item.cycle < 99 if item.passes else None,
                    targetname=item.label,
                    targetuuid=self.labeldict[item.label],
                    tooltip="",
                    tooltipshort="",
                )
                newitem.tooltip = executionItemTooltip(newitem, "long")
                newitem.tooltipshort = executionItemTooltip(newitem, "short")
                execution.append(newitem)
                seqId += 1
        if metadata[MetaType.LOOP]:
            for item in metadata[MetaType.LOOP]:
                newitem = LoopItem(
                    type="loop",
                    seqId=seqId,
                    passes=None,
                    nthpass=None,
                    count=item.count,
                    tooltip="",
                    tooltipshort="",
                )
                newitem.tooltip = executionItemTooltip(newitem, "long")
                newitem.tooltipshort = executionItemTooltip(newitem, "short")
                execution.append(newitem)
                seqId += 1
        if metadata[MetaType.DYNAMICS]:
            for item in metadata[MetaType.DYNAMICS]:
                item = cast(DynamicsMeta, item)
                newitem = DynamicsItem(
                    type="dynamics",
                    seqId=seqId,
                    passes=item.passes or None,
                    loops=item.iterations or None,
                    nthpass=item.cycle < 99 if item.passes else None,
                    fromDynamics=(
                        (item.from_abbr.name if isinstance(item.from_abbr, DynamicLevel) else item.from_abbr)
                        if item.from_abbr
                        else None
                    ),
                    toDynamics=item.to_abbr.name if isinstance(item.to_abbr, DynamicLevel) else item.to_abbr,
                    fromValue=self.velocity2frac(item.from_value) if item.from_value is not None else None,
                    toValue=self.velocity2frac(item.to_value),
                    fromSection=item.first_beat if item.last_beat else None,
                    toSection=item.last_beat if item.last_beat else item.first_beat,
                    isGradual=(item.from_value is not None or item.last_beat is not None),
                    positions=item.positions,
                    tooltip="",
                    tooltipshort="",
                )
                newitem.tooltip = executionItemTooltip(newitem, "long")
                newitem.tooltipshort = executionItemTooltip(newitem, "short")
                execution.append(newitem)
                seqId += 1
        if metadata[MetaType.TEMPO]:
            for item in metadata[MetaType.TEMPO]:
                item = cast(TempoMeta, item)
                newitem = TempoItem(
                    type="tempo",
                    seqId=seqId,
                    passes=item.passes or None,
                    loops=item.iterations or None,
                    nthpass=item.cycle < 99 if item.passes else None,
                    fromValue=int(item.from_value) if item.from_value is not None else None,
                    toValue=int(item.to_value),
                    fromSection=item.first_beat if item.last_beat else None,
                    toSection=item.last_beat if item.last_beat else item.first_beat,
                    isGradual=(item.explicit_gradual or item.from_value is not None or item.last_beat is not None),
                    tooltip="",
                    tooltipshort="",
                )
                newitem.tooltip = executionItemTooltip(newitem, "long")
                newitem.tooltipshort = executionItemTooltip(newitem, "short")
                execution.append(newitem)
                seqId += 1
        return execution

    def append_system_info(self, gongan: Gongan):
        """Appends a beat to the JSON structure."""
        uuid = self.uuiddict[gongan.id]
        if gongan.metadata[MetaType.PART]:
            self.current_part = cast(PartMeta, gongan.metadata[MetaType.PART][0]).name
        if self.current_part:
            part = self.score.parts[self.current_part]
            part.append(uuid)

        label = gongan.metadata[MetaType.LABEL][0].name if gongan.metadata[MetaType.LABEL] else None
        colwidths = [max([len(beat.get_notes(pos)) for pos in beat.measures.keys()]) for beat in gongan.beats]

        system = System(
            uuid=uuid,
            id=gongan.id,
            index=gongan.id - 1,
            label=label.title() if label in self.labeldict.keys() else None,
            execution=self.get_execution(gongan.metadata),
            staffs={
                pos: [
                    Measure(notation=[n.symbol for n in beat.measures[pos].passes[-1].notes]) for beat in gongan.beats
                ]
                # pylint: disable=protected-access
                # pylint: disable=no-member
                for pos in sorted(self.positions, key=Position._member_names_.index)
            },
            colWidths=colwidths,
        )
        # pylint: disable=no-member
        self.score.systems.append(system)

    def save_to_json(self):
        """Saves the JSONized score to file. The file is saved in compact form for production."""
        indent = None
        dictized = self.score.model_dump(exclude_none=True)
        # if self.run_settings.options.notation_to_midi.run_type is not RunType.PRODUCTION:
        # indent = 4
        indent = 4
        jsonized = json.dumps(dictized, indent=indent, cls=CompactEncoder)
        with open(self.run_settings.json_out_filepath, "w", encoding="UTF-8") as outfile:
            outfile.writelines(jsonized)
        dictized = self.score.model_dump(exclude_none=True)
        # if self.run_settings.options.notation_to_midi.run_type is not RunType.PRODUCTION:
        # indent = 4
        indent = 4
        jsonized = json.dumps(dictized, indent=indent, cls=CompactEncoder)
        with open(self.run_settings.json_out_filepath, "w", encoding="UTF-8") as outfile:
            outfile.writelines(jsonized)
