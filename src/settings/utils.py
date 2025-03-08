from itertools import product

from src.common.constants import (  # pylint: disable=unused-import
    InstrumentGroup,
    InstrumentType,
    NotationEnum,
    Position,
)
from src.settings.classes import RunSettings
from src.settings.constants import InstrumentTagFields


def pretty_compact_json(obj, _key: str = "root", _level: int = 0, _is_last: bool = False) -> list:
    """Saves a json-like structure in a semi-compact form to keep it human-readable.
       The function keeps structures as much as possible on one line. Exceptions:
       - If the items of a structure contain only "complex" (dict or list) values, each item will be written on
          a separate line.
       - Both rules can be overruled with the lists `treat_as_complex` and `treat_as_simple` (see code).

    Args:
        obj (Any): The root object of the structure.
        _key (str, optional): The key value of the item. Defaults "root". Only to be used in recursive call.
        _level (int, optional): nesting level, used for indenting. Defaults to 0. Only to be used in  recursive call.
        _is_last (bool, optional): last element of a list or dict. Defaults to False. Only to be used in  recursive
        call.

    Returns:
        list: _description_
    """
    indent = " " * 8
    treat_as_complex = _key in ["root", "markers", "highlight"]
    treat_as_simple = _key in []
    match obj:
        case None:
            return "null"
        case dict() | list():
            islist = isinstance(obj, list)
            b_, _b = ("[", "]") if islist else ("{", "}")

            if not obj:
                return b_ + _b

            if isinstance(obj, dict):
                lastkey = list(obj.items())[-1][0]
                items_to_str = [
                    f'"{key}": {pretty_compact_json(val, key, _level+1, key==lastkey)}' for key, val in obj.items()
                ]
            else:
                lastvalue = obj[-1]
                items_to_str = [pretty_compact_json(val, _key, _level + 1, val == lastvalue) for val in obj]

            is_complex = all(type(it) in [type(dict()), type(list())] for it in (obj if islist else obj.values()))
            is_complex = (is_complex or treat_as_complex) and not treat_as_simple
            # new line + level indent after last element
            sep0 = "\n" + indent * (_level) if is_complex and _is_last else ""  # new
            # new line + level-1 indent after closing bracket following last element
            sep_1 = "\n" + indent * max(_level - 1, 0) if is_complex and _is_last else ""
            # new line + level indent after any other element
            sep1 = "\n" + indent * (_level + 1) if is_complex else ""
            return f"{b_}{sep1}" + f", {sep1}".join(items_to_str) + f"{sep0}{_b}{sep_1}"
        case bool():
            return str(obj).lower()
        case int() | float():
            return f"{obj}"
        case str():
            return f'"{obj}"'


def tag_to_position_dict(run_settings: RunSettings) -> dict[str, list[Position]]:
    """Creates a dict that converts the instrumenttag settings table to a mapping tag -> list[Position].
       Tag alternatives are separated by a pipe symbol (|). Possible additional tags are given in the
       `addition` data field. These should follow the tag immediately or separated by a single space.
    Args:  run_settings (RunSettings):
    Returns (dict[str, list[Position]]):
    """
    # pylint: disable=invalid-name
    TAG = InstrumentTagFields.TAG
    POS = InstrumentTagFields.POSITIONS
    GROUPS = InstrumentTagFields.GROUPS
    ADD = InstrumentTagFields.ADDITION
    # pylint: enable=invalid-name

    # filter records for the current instrumentgroup value.
    tag_rec_list = [
        record.copy() for record in run_settings.data.instrument_tags if run_settings.instrumentgroup in record[GROUPS]
    ]
    # split the `tag` and `addition` fields and explode the data for each combination of tag and addition
    # combine both part with different separators. Store the result into a lookup dict.
    separators = ["", " ", "_"]
    lookup_dict = {
        (tag + sep + add): record[POS]
        for record in tag_rec_list
        for tag, add in product(record[TAG].split("|"), record[ADD].split("|"))
        for sep in (separators if add else [""])
    }
    # Add all uppercase variants
    lookup_dict |= {tag.upper(): val for tag, val in lookup_dict.items()}
    # Add the string values of all Position and Instrumenttype members as tags
    lookup_dict |= {instr: [pos for pos in Position if pos.instrumenttype == instr] for instr in InstrumentType}
    lookup_dict |= {TAG: [pos] for pos in Position}

    return lookup_dict


if __name__ == "__main__":
    pass
