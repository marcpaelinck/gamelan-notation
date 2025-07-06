import os
from typing import override

from src.notation2midi.classes import Agent
from src.settings.classes import Content, PartForm, RunSettings, Song
from src.settings.constants import PresetsFields
from src.settings.utils import pretty_compact_json


class MidiPlayerUpdateAgentModel(Agent):
    """Model for agents that update the content.json file in the midiplayer data folder.
    This class should be subclassed, see subclass definitions below"""

    def _get_midiplayer_content(self, datafolder: str, filename: str) -> Content:
        """Loads the configuration file for the JavaScript midplayer app.
        Next to settings, the file contains information about the MIDI and PDF files
        in the app's production folder.
        Returns:
            Content: Structure for the midiplayer content.
        """
        with open(os.path.join(datafolder, filename), "r", encoding="utf-8") as filename:
            playercontent = filename.read()
        # return temp_update_me(Content.model_validate_json(playercontent))
        return Content.model_validate_json(playercontent)

    def _save_midiplayer_content(self, playercontent: Content, datafolder: str, filename: str):
        """Saves the configuration file for the JavaScript midplayer app.
        Args:
            playercontent (Content): content that should be saved to the config file.
            filename (str, optional): name of the config file. Defaults to None.
        """
        playercontent.songs = sorted(playercontent.songs, key=lambda s: s.title)
        contentfilepath = os.path.join(datafolder, filename)
        tempfilepath = os.path.join(datafolder, "_" + filename)
        try:
            with open(tempfilepath, "w", encoding="utf-8") as outfile:
                jsonised = pretty_compact_json(playercontent.model_dump())
                outfile.write(jsonised)
        except IOError as e:
            os.remove(tempfilepath)
            self.logerror(e)
        else:
            os.remove(contentfilepath)
            os.rename(tempfilepath, contentfilepath)

    def _update_instrument_info(self, content: Content) -> None:
        """Updates the MIDI information of the InstrumentInfo component from the presets config file."""
        instrument_presets = self.run_settings.data.presets
        for instrumentgroup, instrumentinfo in content.instrumentgroups.items():
            for instrument in instrumentinfo:
                # instrument.group of the content can correspond either with an instrument type
                # or an instrument position.
                # 1. Try matching with instrument type
                presets = [
                    preset
                    for preset in instrument_presets
                    if preset[PresetsFields.GROUP] == instrumentgroup
                    and preset[PresetsFields.INSTRUMENTTYPE] == instrument.group
                ]
                if presets:
                    instrument.channels = [preset[PresetsFields.CHANNEL] for preset in presets]
                    preset = presets[0]
                    instrument.preset = preset[PresetsFields.PRESET]
                    instrument.bank = preset[PresetsFields.BANK]
                    instrument.midioffset = preset[PresetsFields.MIDIOFFSET]
                # 2. Try matching with instrument position
                presets = [
                    preset
                    for preset in instrument_presets
                    if preset[PresetsFields.GROUP] == instrumentgroup
                    and preset[PresetsFields.POSITION] == instrument.group
                ]
                if presets:
                    instrument.channels = [preset[PresetsFields.CHANNEL] for preset in presets]
                    preset = presets[0]
                    instrument.preset = preset[PresetsFields.PRESET]
                    instrument.bank = preset[PresetsFields.BANK]
                    instrument.midioffset = preset[PresetsFields.MIDIOFFSET]


class MidiPlayerUpdatePartAgent(MidiPlayerUpdateAgentModel):
    """Updates the Part info in the content.json file in the midiplayer data folder."""

    LOGGING_MESSAGE = "UPDATING PART INFO IN MIDI PLAYER CONTENT"
    EXPECTED_INPUT_TYPES = (
        Agent.InputOutputType.RUNSETTINGS,
        Agent.InputOutputType.PART,
    )
    RETURN_TYPE = None

    def __init__(self, run_settings: RunSettings, part: PartForm):
        super().__init__(run_settings)
        self.part_info = part

    @override
    @classmethod
    def run_condition_satisfied(cls, run_settings: RunSettings):
        return (
            run_settings.options.notation_to_midi.is_production_run
            and run_settings.options.notation_to_midi.save_midifile
        )

    @override
    def _main(self) -> None:
        """Updates the Part information of the song in the content.json file of the midi player."""

        content = self._get_midiplayer_content(
            self.run_settings.midiplayer.folder, self.run_settings.midiplayer.contentfile
        )
        self._update_instrument_info(content)

        # If info is already present, replace it.
        song_title = self.run_settings.notationfile.title
        player_song: Song = next((song_ for song_ in content.songs if song_.title == song_title), None)
        if not player_song:
            # TODO create components of Song
            content.songs.append(
                player_song := Song(
                    title=self.run_settings.notationfile.title,
                    instrumentgroup=self.run_settings.instrumentgroup,
                    display=True,
                    pfd=None,
                )
            )
            self.loginfo("New song %s created for MIDI player content", player_song.title)

        # pylint: disable=not-an-iterable
        # pylint gets confused by assignment of Field() to Pydantic member Song.parts
        part = next((part_ for part_ in player_song.parts if part_.part == self.part_info.part), None)
        if part:
            part.file = self.part_info.file or part.file
            part.loop = self.part_info.loop or part.loop
            part.markers = self.part_info.markers or part.markers
            self.loginfo("Existing part %s updated for MIDI player content", part.part)
        else:
            if self.part_info.file:
                # pylint gets confused by Pydantic Field() assignment to Song.part in Song class definition.
                player_song.parts.append(self.part_info)  # pylint: disable=no-member
                self.loginfo("New part %s created for MIDI player content", self.part_info.part)
            else:
                self.logerror(
                    "Can't add new part info '%s' to the midiplayer content: missing midifile information. "
                    "Please run again with run-option `save_midifile` set.",
                    self.part_info.part,
                )
        self._save_midiplayer_content(
            content, self.run_settings.midiplayer.folder, self.run_settings.midiplayer.contentfile
        )


class MidiPlayerUpdatePdfAgent(MidiPlayerUpdateAgentModel):
    """Updates the PDF info in the content.json file in the midiplayer data folder."""

    LOGGING_MESSAGE = "UPDATING PDF INFO IN MIDI PLAYER CONTENT"
    EXPECTED_INPUT_TYPES = (
        Agent.InputOutputType.RUNSETTINGS,
        Agent.InputOutputType.PDFFILE,
    )
    RETURN_TYPE = None

    def __init__(self, run_settings: RunSettings, pdf_file: str):
        super().__init__(run_settings)
        self.pdf_file = pdf_file

    @override
    @classmethod
    def run_condition_satisfied(cls, run_settings: RunSettings):
        return (
            run_settings.options.notation_to_midi.is_production_run
            and run_settings.options.notation_to_midi.save_pdf_notation
            and run_settings.part_id == run_settings.notationfile.generate_pdf_part_id
        )

    @override
    def _main(self) -> None:
        """Updates the PDF information of the song in the content.json file of the midi player."""
        content = self._get_midiplayer_content(
            self.run_settings.midiplayer.folder, self.run_settings.midiplayer.contentfile
        )
        # Check if song info is already present in the content file
        song_title = self.run_settings.notationfile.title
        player_song: Song = next((song_ for song_ in content.songs if song_.title == song_title), None)
        if player_song:
            player_song.pdf = self.pdf_file
            player_song.notation_version = self.run_settings.notation_version
        else:
            # Create a new song entry
            # TODO create components of Song
            content.songs.append(
                player_song := Song(
                    title=self.run_settings.notationfile.title,
                    instrumentgroup=self.run_settings.instrumentgroup,
                    display=True,
                    pfd=self.pdf_file,
                    notation_version=self.run_settings.notation_version,
                )
            )
            self.loginfo("New song %s created for MIDI player content", player_song.title)

        content.songs = sorted(content.songs, key=lambda s: s.title)
        self._save_midiplayer_content(
            content, self.run_settings.midiplayer.folder, self.run_settings.midiplayer.contentfile
        )
