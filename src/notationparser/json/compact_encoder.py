import json
from re import compile as reCompile
from typing import Type, override

from _ctypes import PyObj_FromPtr


class Compact(object):
    """Value wrapper. See explanation below."""

    def __init__(self, value):
        self.value = value


class CompactEncoder(json.JSONEncoder):
    """Enables to specify the output format of the Pydantic model_dump method for specific elements of the object structure.
    The elements should be wrapped in a Compact object. The wrapper acts as a label that can be detected in a @field_serializer
    method of a Pydantic class.
    Note: the encoder only seems to work with json.dumps, not with json.dump.
    See https://stackoverflow.com/questions/13249415/how-to-implement-custom-indentation-when-pretty-printing-with-the-json-module
    """

    FORMAT_SPEC = "@@{}@@"
    regex = reCompile(FORMAT_SPEC.format(r"(\d+)"))

    def __init__(self, **kwargs):
        # Save copy of any keyword argument values needed for use here.
        self.__sort_keys = kwargs.get("sort_keys", None)
        super(CompactEncoder, self).__init__(**kwargs)

    @override
    def default(self, o):
        return self.FORMAT_SPEC.format(id(o)) if isinstance(o, Compact) else super(CompactEncoder, self).default(o)

    @override
    def encode(self, o):
        format_spec = self.FORMAT_SPEC  # Local var to expedite access.
        json_repr = super(CompactEncoder, self).encode(o)  # Default JSON.

        # Replace any marked-up object ids in the JSON repr with the
        # value returned from the json.dumps() of the corresponding
        # wrapped Python object.
        for match in self.regex.finditer(json_repr):
            # see https://stackoverflow.com/a/15012814/355230
            id = int(match.group(1))
            no_indent = PyObj_FromPtr(id)
            json_obj_repr = json.dumps(no_indent.value, sort_keys=self.__sort_keys)

            # Replace the matched id string with json formatted representation
            # of the corresponding Python object.
            json_repr = json_repr.replace('"{}"'.format(format_spec.format(id)), json_obj_repr)

        return json_repr
