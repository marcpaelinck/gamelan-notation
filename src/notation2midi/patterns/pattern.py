from src.common.notes import Note
from src.settings.classes import RunSettings


class PatternGenerator:

    def __init__(self, run_settings: RunSettings):
        self.run_settings = run_settings

    # Override this in each subclass
    def create_pattern(self, notes: list[Note]) -> None: ...
