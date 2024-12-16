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
