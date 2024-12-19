f"""Separate location for lookup tables, which are populated with methods in utils.py.
    This construct enables to avoid circular references when importing the variables.
"""

import csv

import numpy as np
import pandas as pd

from src.common.classes import InstrumentTag, Preset
from src.common.constants import DynamicLevel, InstrumentGroup, InstrumentType, Position
from src.common.logger import get_logger
from src.settings.classes import RunSettings
from src.settings.constants import InstrumentTagFields, PresetsFields
from src.settings.settings import get_run_settings

logger = logger = get_logger(__name__)


class Lookup:
    TAG_TO_POSITION: dict[InstrumentTag, list[Position]] = dict()  # KEEP

    def __init__(self, run_settings: RunSettings) -> None:
        """Initializes lookup dicts and lists from settings files

        Args:
            instrumentgroup (InstrumentGroup): The type of orchestra (e.g. gong kebyar, semar pagulingan)
            version (Version):  Used to define which midi mapping to use from the midinotes.csv file.

        """
        self.TAG_TO_POSITION.update(self._create_tag_to_position_lookup(run_settings.instruments))

    def _create_instrumentposition_to_preset_lookup(
        self, instrumentgroup: InstrumentGroup, fromfile: str
    ) -> dict[InstrumentType, Preset]:
        presets_df = pd.read_csv(fromfile, sep="\t", quoting=csv.QUOTE_NONE)
        # Fill in empty position fields with a list of all positions for the instrument type.
        # Then "explode" (repeat row for each element in the position list)
        # TODO not yet working!!!!
        mask = presets_df[PresetsFields.POSITION].isnull()
        presets_df.loc[mask, PresetsFields.POSITION] = presets_df.loc[mask, PresetsFields.INSTRUMENTTYPE].apply(
            lambda x: [p for p in Position if p.instrumenttype == x]
        )
        presets_df = presets_df.explode(column=PresetsFields.POSITION, ignore_index=True)
        # self.create a dict and cast items to Preset objects.
        presets_obj = (
            presets_df[presets_df[PresetsFields.INSTRUMENTGROUP] == instrumentgroup.value]
            .drop(PresetsFields.INSTRUMENTGROUP, axis="columns")
            .to_dict(orient="records")
        )
        presets = [Preset.model_validate(preset) for preset in presets_obj]
        return {preset.position: preset for preset in presets}

    def _create_tag_to_position_lookup(
        self,
        instruments: RunSettings.InstrumentInfo,
    ) -> dict[InstrumentTag, list[Position]]:
        """self.creates a dict that maps "free style" position tags to a list of InstumentPosition values

        Args:
            fromfile (str, optional): _description_. Defaults to TAGS_DEF_FILE.

        Returns:
            _type_: _description_
        """
        try:
            tags_dict = (
                pd.read_csv(instruments.tag_filepath, sep="\t")
                .drop(columns=[InstrumentTagFields.INFILE])
                .to_dict(orient="records")
            )
        except:
            logger.error(
                f"Error importing file {instruments.tag_filepath}. Check that it exists and that it is properly formatted."
            )
        tags_dict = (
            tags_dict
            + [
                {
                    InstrumentTagFields.TAG: instr,
                    InstrumentTagFields.POSITIONS: [pos for pos in Position if pos.instrumenttype == instr],
                }
                for instr in InstrumentType
            ]
            + [{InstrumentTagFields.TAG: pos, InstrumentTagFields.POSITIONS: [pos]} for pos in Position]
        )
        tags = [InstrumentTag.model_validate(record) for record in tags_dict]

        lookup_dict = {t.tag: t.positions for t in tags}

        return lookup_dict


run_settings = get_run_settings()
LOOKUP = Lookup(run_settings)
x = 1
