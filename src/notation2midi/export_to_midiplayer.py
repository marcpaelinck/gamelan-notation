import os
import time

from src.notation2midi.classes import ParserModel
from src.settings.classes import Content, PartForm, Song
from src.settings.settings import Settings
from src.settings.utils import pretty_compact_json


class MidiPlayerExportAgent(ParserModel):

    #     title=self.run_settings.notation.title,
    # group=self.run_settings.notation.instrumentgroup,
    # pdf_file=self.score.settings.pdf_out_file,
    # notation_version=notation_version,

    # def _update_midiplayer_content(self) -> None:
    #     Settings.update_midiplayer_content(
    #         title=self.run_settings.notation.title,
    #         group=self.run_settings.notation.instrumentgroup,
    #         partinfo=PartForm(
    #             part=self.part_info.part,
    #             file=self.part_info.file,
    #             loop=self.part_info.loop,
    #             markers=self.sorted_markers_millis_to_frac(self.part_info.markers, self.score.midifile_duration),
    #         ),

    def __init__(self, part: PartForm = None, pdf_file: str = None):
        super().__init__(self.ParserType.SCOREGENERATOR, Settings.get())
        self.part_info = part
        self.pdf_file = pdf_file

    def _temp_update_me(self, content: Content):
        """Auxiliary function that updates the content with the pdf version"""
        # use only during development. #
        settings = Settings.get()
        for song in content.songs:
            notation_info = next(
                (notation for key, notation in settings.configdata.notations.items() if notation.title == song.title),
                None,
            )
            if song.pdf and notation_info:
                filepath = os.path.join(notation_info.folder_in, notation_info.parts["full"].file)
                modification_time = os.path.getmtime(filepath)
                version_date = time.strftime(settings.pdf_converter.version_fmt, time.gmtime(modification_time)).lower()
                song.notation_version = version_date
        return content

    def _save_midiplayer_content(self, playercontent: Content, datafolder: str, filename: str):
        """Saves the configuration file for the JavaScript midplayer app.
        Args:
            playercontent (Content): content that should be saved to the config file.
            filename (str, optional): name of the config file. Defaults to None.
        """
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

    @ParserModel.main
    def update_midiplayer_content(self) -> None:
        """Updates the information given in Part in the content.json file of the midi player.

        Args:
            title (str): Title of the `song`, should be taken from run_settings.notation.title.
            group (InstrumentGroup)fpar:
            part (Part): Information that should be stored/updated. Attributes of `part` equal to None
                        will not be modified in contents.json.
        """
        if not (
            self.run_settings.options.notation_to_midi.update_midiplayer_content
            and self.run_settings.notation.include_in_production_run
        ):
            return False
        settings = Settings.get()
        content = self._get_midiplayer_content(settings.midiplayer.folder, settings.midiplayer.contentfile)
        # If info is already present, replace it.
        song_title = self.run_settings.notation.title
        player_song: Song = next((song_ for song_ in content.songs if song_.title == song_title), None)
        if not player_song:
            # TODO create components of Song
            content.songs.append(
                player_song := Song(
                    title=self.run_settings.notation.title,
                    instrumentgroup=self.run_settings.instrumentgroup,
                    display=True,
                    pfd=self.pdf_file,
                    notation_version=self.run_settings.notation_version,
                )
            )
            self.loginfo("New song %s created for MIDI player content", player_song.title)
        elif self.pdf_file:
            player_song.pdf = self.pdf_file
        if self.run_settings.notation_id == "full":
            player_song.notation_version = self.run_settings.notation_version

        if self.part_info:
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
        self._save_midiplayer_content(content, settings.midiplayer.folder, settings.midiplayer.contentfile)

        if self.has_errors:
            return False
        return True
