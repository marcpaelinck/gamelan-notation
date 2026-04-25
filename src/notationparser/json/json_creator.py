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
    ExecutionItem,
    ExecutionItemBase,
    GotoItem,
    KempliItem,
    LoopItem,
    Measure,
    Score,
    SequenceItem,
    SuppressItem,
    System,
    TempoItem,
    WaitItem,
)
from src.notationparser.metadata_classes import (
    DynamicsMeta,
    MetaDataSwitch,
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
        labels = set([label.name for gongan in pscore.gongans for label in gongan.metadata[MetaType.LABEL]])
        # Only keep labels that are used for Goto metadata. This will omit labels used for Copy metadata.
        labeldict = {
            gongan.metadata[MetaType.LABEL][0].name: uuiddict[gongan.id]
            for gongan in pscore.gongans
            if gongan.metadata[MetaType.LABEL] and gongan.metadata[MetaType.LABEL][0].name in labels
        }
        return (uuiddict, labeldict)

    def velocity2frac(self, velocity: int) -> float:
        return round(velocity / 127, 2)

    def getSeqId(self, item: ExecutionItem):
        typeSeq = {
            "loop": 1000,
            "tempo": 2000,
            "dynamics": 3000,
            "wait": 4000,
            "goto": 5000,
            "sequence": 6000,
            "kempli": 7000,
            "suppress": 8000,
        }[item.type]
        beatSeq = 100 * ((item.fromSection or item.section if hasattr(item, "fromSection") else None) or 0)
        passesSeq = 10 * min(item.passes or [0])
        iterSeq = min(item.iterations or [0]) if hasattr(item, "iterations") else 0
        return typeSeq + beatSeq + passesSeq + iterSeq

    def get_execution(self, metadata: dict[MetaType, list[MetaDataType]]) -> list[ExecutionItemBase]:
        execution = []
        for metatype in [
            MetaType.GOTO,
            MetaType.LOOP,
            MetaType.WAIT,
            MetaType.DYNAMICS,
            MetaType.TEMPO,
            MetaType.SEQUENCE,
            MetaType.KEMPLI,
            MetaType.SUPPRESS,
        ]:
            for item in metadata[metatype]:
                newitem = None
                match (metatype):
                    case MetaType.GOTO:
                        newitem = GotoItem(
                            type="goto",
                            passes=item.passes or None,
                            nthpass=item.cycle < 99 if item.passes else None,
                            targetname=item.label,
                            targetuuid=self.labeldict[item.label],
                            tooltip="",
                            tooltipshort="",
                        )
                    case MetaType.LOOP:
                        newitem = LoopItem(
                            type="loop",
                            passes=item.passes or None,
                            nthpass=item.cycle < 99 if item.passes else None,
                            count=item.count,
                            tooltip="",
                            tooltipshort="",
                        )
                    case MetaType.SEQUENCE:
                        newitem = SequenceItem(
                            type="sequence",
                            labels=item.value,
                            uuids=[self.labeldict[label] for label in item.value],
                            passes=None,
                            nthpass=None,
                            tooltip="",
                            tooltipshort="",
                        )
                    case MetaType.KEMPLI:
                        if item.status != MetaDataSwitch.ON:
                            # ON is the default value
                            newitem = KempliItem(
                                type="kempli",
                                value=item.status,
                                beats=item.beats or None,
                                passes=item.passes or None,
                                nthpass=item.cycle < 99 if item.passes else None,
                                iterations=None,
                                tooltip="",
                                tooltipshort="",
                            )
                    case MetaType.SUPPRESS:
                        newitem = SuppressItem(
                            type="suppress",
                            positions=item.positions,
                            passes=item.passes or None,
                            nthpass=item.cycle < 99 if item.passes else None,
                            beats=item.beats or None,
                            iterations=None,
                            tooltip="",
                            tooltipshort="",
                        )
                    case MetaType.WAIT:
                        newitem = WaitItem(
                            type="wait",
                            seconds=item.seconds,
                            passes=item.passes or None,
                            nthpass=item.cycle < 99 if item.passes else None,
                            tooltip="",
                            tooltipshort="",
                        )
                    case MetaType.DYNAMICS:
                        item = cast(DynamicsMeta, item)
                        newitem = DynamicsItem(
                            type="dynamics",
                            passes=item.passes or None,
                            iterations=item.iterations or None,
                            nthpass=item.cycle < 99 if item.passes else None,
                            fromDynamics=(
                                (item.from_abbr.name if isinstance(item.from_abbr, DynamicLevel) else item.from_abbr)
                                if item.from_abbr
                                else None
                            ),
                            dynamics=item.to_abbr.name if isinstance(item.to_abbr, DynamicLevel) else item.to_abbr,
                            fromValue=self.velocity2frac(item.from_value) if item.from_value is not None else None,
                            value=self.velocity2frac(item.to_value),
                            fromSection=(
                                (item.first_beat or 1)
                                if ((item.beat_count and item.last_beat) or item.explicit_gradual)
                                else None
                            ),
                            # (values.fromValue as number) || (values.isGradual ? 1 : (values.value as number)),
                            section=(
                                item.last_beat
                                if item.last_beat is not None
                                else item.first_beat + (item.beat_count - 1 if item.beat_count else 0)
                            ),
                            isGradual=(
                                item.explicit_gradual
                                or (item.from_value is not None and item.last_beat is not None)
                                or item.last_beat is not None
                                or (item.beat_count > 0)
                            ),
                            positions=item.positions,
                            tooltip="",
                            tooltipshort="",
                        )
                    case MetaType.TEMPO:
                        item = cast(TempoMeta, item)
                        newitem = TempoItem(
                            type="tempo",
                            passes=item.passes or None,
                            iterations=item.iterations or None,
                            nthpass=item.cycle < 99 if item.passes else None,
                            fromValue=int(item.from_value) if item.from_value is not None else None,
                            value=int(item.to_value),
                            fromSection=(
                                (item.first_beat or 1)
                                if ((item.beat_count and item.last_beat) or item.explicit_gradual)
                                else None
                            ),
                            section=(
                                item.last_beat
                                if item.last_beat is not None
                                else item.first_beat + (item.beat_count - 1 if item.beat_count else 0)
                            ),
                            isGradual=(
                                item.explicit_gradual
                                or (item.from_value is not None and item.last_beat is not None)
                                or (item.beat_count > 0)
                            ),
                            tooltip="",
                            tooltipshort="",
                        )
                    case _:
                        pass
                if newitem:
                    newitem.tooltip = executionItemTooltip(newitem, "long")
                    newitem.tooltipshort = executionItemTooltip(newitem, "short")
                    newitem.seqId = self.getSeqId(newitem)
                    execution.append(newitem)
        execution.sort(key=lambda el: el.seqId)
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
                    Measure(notation=[n.symbol for n in beat.measures[pos].passes[-1].notes])
                    for beat in gongan.beats
                    if not beat.is_waitmeta_beat
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
        jsonpathname = self.run_settings.json_out_filepath.replace(" [full]", "")
        with open(jsonpathname, "w", encoding="UTF-8") as outfile:
            outfile.writelines(jsonized)
