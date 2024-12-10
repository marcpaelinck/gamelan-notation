import os

from pydantic import BaseModel, Field

from src.common.constants import AnimationProfiles, InstrumentGroup, NoteOct, Stroke


class Part(BaseModel):
    name: str
    file: str
    loop: bool
    markers: dict[str, float] = Field(default_factory=dict)  # {partname: milliseconds}


class InstrumentInfo(BaseModel):
    name: str
    channels: list[int]
    midioffset: int
    animation: AnimationProfiles


class Profile(BaseModel):
    file: str
    notes: dict[NoteOct, list[int | None]]
    strokes: list[Stroke]


class AnimationInfo(BaseModel):
    highlight: dict[Stroke, list[str]]
    profiles: dict[AnimationProfiles, Profile]


class Song(BaseModel):
    title: str
    instrumentgroup: InstrumentGroup
    display: bool
    parts: list[Part] = Field(default_factory=list)


class Content(BaseModel):
    songs: list[Song]
    instrumentgroups: dict[InstrumentGroup, list[InstrumentInfo]]
    animation: AnimationInfo
    soundfont: str


if __name__ == "__main__":
    DATAFOLDER = "./data/midiplayer"
    with open(os.path.join(DATAFOLDER, "content.json"), "r") as contentfile:
        result = contentfile.read()
        content = Content.model_validate_json(result)
        print(content)
