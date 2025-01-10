"""This module can be used performs multiple run cycles.
"""

from src.notation2midi.main import load_and_validate_run_settings, notation_to_midi
from src.settings.constants import Yaml
from src.settings.settings import get_all_notation_parts


def multiple_notations_to_midi(notations: list[str, str]):
    """Creates multiple notations

    Args:
        notations (list[tuple[str, str]]): list of (composition, part) pairs
    """
    for notation in notations:
        run_settings = load_and_validate_run_settings(notation)
        notation_to_midi(run_settings)


if __name__ == "__main__":
    notations = [
        {Yaml.COMPOSITION: "sinomladrang-sp", Yaml.PART: "full"},
        {Yaml.COMPOSITION: "sinomladrang-sp", Yaml.PART: "pengawak"},
        {Yaml.COMPOSITION: "sinomladrang-sp", Yaml.PART: "pengecet"},
        {Yaml.COMPOSITION: "sinomladrang-gk", Yaml.PART: "full"},
        {Yaml.COMPOSITION: "lengker", Yaml.PART: "full"},
        {Yaml.COMPOSITION: "lengker", Yaml.PART: "penyalit"},
        {Yaml.COMPOSITION: "lengker", Yaml.PART: "pengecet"},
        {Yaml.COMPOSITION: "lengker", Yaml.PART: "pengawak"},
        {Yaml.COMPOSITION: "godekmiring", Yaml.PART: "full"},
        {Yaml.COMPOSITION: "godekmiring", Yaml.PART: "penyalit"},
        {Yaml.COMPOSITION: "godekmiring", Yaml.PART: "pengecet"},
        {Yaml.COMPOSITION: "godekmiring", Yaml.PART: "penyalit-angsel"},
        {Yaml.COMPOSITION: "godekmiring", Yaml.PART: "pengawak"},
        {Yaml.COMPOSITION: "cendrawasih", Yaml.PART: "full"},
    ]
    notations = get_all_notation_parts()

    multiple_notations_to_midi(notations)
