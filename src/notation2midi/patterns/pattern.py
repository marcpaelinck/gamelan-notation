from src.common.notes import Note
from src.settings.classes import RunSettings


class PatternGenerator:

    NAME = "GENERIC PATTERN GENERATOR"  # replace in each subclassed rule

    def __init__(self, run_settings: RunSettings):
        self.run_settings = run_settings

    @classmethod
    def notes_to_str(cls, notes: list[Note]) -> str:
        """Returns the concatenated symbols of the given list of notes"""
        try:
            return "".join([note.symbol for note in notes])
        except:  # pylint: disable=bare-except
            return ""

    def create_pattern(self, notes: list[Note]) -> None:
        """Override this method in each subclass"""
