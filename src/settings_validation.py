""" Validates the definitions in the settings folder
"""

from collections import defaultdict
from pprint import pprint

from src.notation_classes import Character


def check_unique_character_values(musicfont: list[Character]):
    typedict = defaultdict(list)
    for c in musicfont:
        typedict[c.value, c.duration, c.rest_after].append(c.symbol)
    duplicates = {key: val for key, val in typedict.items() if len(val) > 1}
    print(f"DUPLICATE CHARACTER VALUES: {"" if duplicates else "NONE"}")
    if duplicates:
        pprint(duplicates)


def validate_settings(musicfont: list[Character]):
    print("======== SETTINGS VALIDATION ========")
    check_unique_character_values(musicfont)
    print("====================================")
