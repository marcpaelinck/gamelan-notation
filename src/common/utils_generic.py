import json
import re
from enum import StrEnum


def to_list(value, el_type: type):
    # This method tries to to parse a string or a list of strings
    # into a list of `el_type` values.
    # el_type can only be `float` or a subclass of `StrEnum`.
    if isinstance(value, str):
        # Single string representing a list of strings: parse into a list of strings
        # First add double quotes around each list element.
        val = re.sub(r"([A-Za-z_][\w]*)", r'"\1"', value)
        value = json.loads(val)
    if isinstance(value, list):
        # List of strings: convert strings to enumtype objects.
        if all(isinstance(el, str) for el in value):
            return [el_type[el] if issubclass(el_type, StrEnum) else float(el) for el in value]
        elif all(isinstance(el, el_type) for el in value):
            # List of el_type: do nothing
            return value
    else:
        raise ValueError(f"Cannot convert value {value} to a list of {el_type}")


def create_tag_to_position_lookup(tag_records: list[dict[str, str]]):  # -> dict[str, list[Position]]:
    """Creates a dict that maps 'free format' position tags to a list of Position values.
    A tag can represent multiple positions, e.g. the tag `gangsa` maps to the list
    [PEMADE_POLOS, PEMADE_SANGSIH, KANTILAN_POLOS, KANTILAN_SANGSIH]

    Args:
        tag_records (list[dict[str, str]]): 'flat' records representing the input file contents.

    Returns:
        dict[InstrumentTag, list[Position]]: Lookup dict that converts tags to a list of Position values.
    """
    from src.common.classes import InstrumentTag
    from src.common.constants import InstrumentType, Position

    # Validate the values with Pydantic
    try:
        tags = [InstrumentTag.model_validate(record) for record in tag_records]
    except Exception as e:
        raise Exception(str(e))
    # Add a tag for each InstrumentType value
    tags += [
        InstrumentTag(tag=instr, positions=[pos for pos in Position if pos.instrumenttype == instr])
        for instr in InstrumentType
    ]
    # Add a tag for each Position value
    tags += [InstrumentTag(tag=pos, positions=[pos]) for pos in Position]

    lookup_dict = {t.tag: t.positions for t in tags}

    return lookup_dict
