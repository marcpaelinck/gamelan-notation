import json
import os
from glob import glob
from os import path
from pprint import pprint

import pandas as pd
import regex
from scipy.io import wavfile

from src.common.classes import InstrumentTag, Note
from src.common.constants import (
    InstrumentGroup,
    InstrumentType,
    Modifier,
    Pitch,
    Position,
    Stroke,
)
from src.common.logger import Logging

logger = Logging.get_logger(__name__)


def get_all_tags():
    folder = "G:\\Marc\\documents-backup-2jun24-08h00\\Documents\\administratie\\_VRIJETIJD_REIZEN\\Gamelangroepen\\Studiemateriaal\\Muzieknotatie"
    files = [file for file in glob(path.join(folder, "*.xlsx")) if not path.basename(file).startswith("_")]
    tagdict = dict()
    for file in files:
        taglist = set(pd.read_excel(file).iloc[:, 0].unique())
        tagdict.update({tag: path.basename(file) for tag in taglist if isinstance(tag, str)})
    pprint(sorted(list(tagdict.keys())))
    pprint(tagdict)


def map_positions():
    instrumenttag_dict = pd.read_csv("./settings/instrumenttags_1.csv", sep="\t").to_dict(orient="records")
    tag0 = InstrumentTag.model_validate(instrumenttag_dict[0])
    tags = [InstrumentTag.model_validate(tag) for tag in instrumenttag_dict]
    mapping_r = [
        (
            ["reyong13", "reyong1+3", "reyong 1/3", "reyong p"],
            [Position.REYONG_1, Position.REYONG_3],
        ),
        (
            ["reyong24", "reyong2+4", "reyong 2.4", "reyong s", "reyong 2/4"],
            [Position.REYONG_2, Position.REYONG_4],
        ),
        (["reyong12", "reyong1+2"], [Position.REYONG_1, Position.REYONG_2]),
        (["reyong34", "reyong3+4"], [Position.REYONG_3, Position.REYONG_4]),
        (["reyong1-3"], [Position.REYONG_1, Position.REYONG_3]),
        (["reyong2-4"], [Position.REYONG_2, Position.REYONG_4]),
        (
            ["reyong1-4"],
            [
                Position.REYONG_1,
                Position.REYONG_2,
                Position.REYONG_3,
                Position.REYONG_4,
            ],
        ),
        (["reyong1", "reyong(1)", "reyong 1"], [Position.REYONG_1]),
        (["reyong2", "reyong(2)", "reyong 2"], [Position.REYONG_2]),
        (["reyong3", "reyong(3)", "reyong 3"], [Position.REYONG_3]),
        (["reyong4", "reyong(4)", "reyong 4"], [Position.REYONG_4]),
        (
            ["Reyong", "reyong", "rey/", "/rey", "+rey"],
            [
                Position.REYONG_1,
                Position.REYONG_2,
                Position.REYONG_3,
                Position.REYONG_4,
            ],
        ),
    ]
    mapping_g = [
        (
            ["gangsa p/s"],
            [
                Position.PEMADE_POLOS,
                Position.PEMADE_SANGSIH,
                Position.KANTILAN_POLOS,
                Position.KANTILAN_SANGSIH,
            ],
        ),
        (["gangsa p", "gang p", "ga p", "/ga.p"], [Position.PEMADE_POLOS, Position.KANTILAN_POLOS]),
        (["gangsa s", "ga s"], [Position.PEMADE_SANGSIH, Position.KANTILAN_SANGSIH]),
        (["pemade p"], [Position.PEMADE_POLOS]),
        (["pemade s"], [Position.PEMADE_SANGSIH]),
        (["kantilan p"], [Position.KANTILAN_POLOS]),
        (["kantilan s"], [Position.KANTILAN_SANGSIH]),
        (["pemade"], [Position.PEMADE_POLOS, Position.PEMADE_SANGSIH]),
        (["kantilan"], [Position.KANTILAN_POLOS, Position.KANTILAN_SANGSIH]),
        (
            ["ga ", "ga+", "ga/", "/ga", "/gang", "gang.", "ga4", "gangs4", "gangsa", "(ga)", "/ ga"],
            [
                Position.PEMADE_POLOS,
                Position.PEMADE_SANGSIH,
                Position.KANTILAN_POLOS,
                Position.KANTILAN_SANGSIH,
            ],
        ),
    ]
    for mytag in tags:
        mytag.positions = [Position[instr.value] for instr in mytag.instruments if instr.value in Position]
        for values, positions in mapping_r:
            if any(val in mytag.tag for val in values):
                mytag.positions.extend(positions)
                break
        for values, positions in mapping_g:
            if any(val in mytag.tag for val in values):
                mytag.positions.extend(positions)
                break
    tags_dict = [mytag.model_dump() for mytag in tags]
    logger.info([t.tag for t in tags if not t.positions])
    tags_df = pd.DataFrame.from_records(tags_dict)
    tags_df.sort_values(by="tag", key=lambda col: col.str.lower())
    tags_df.to_csv("./settings/instrumenttags.csv", sep="\t", index=False)


def merge_parts(datapath: str, basefile: str, mergefile: str, resultfile: str):
    columns = ["tag"] + ["BEAT" + str(i) for i in range(1, 33)]
    sortingorder = [
        "comment",
        "metadata",
        "ugal",
        "gangsa p",
        "gangsa s",
        "reyong1-4",
        "reyong1",
        "reyong2",
        "reyong3",
        "reyong4",
        "calung",
        "jegog",
        "gong",
        "kendang",
    ]
    # Load the scores in dataframes
    base_df = pd.read_csv(
        path.join(datapath, basefile), sep="\t", names=columns, skip_blank_lines=False, encoding="UTF-8"
    )
    merge_df = pd.read_csv(
        path.join(datapath, mergefile), sep="\t", names=columns, skip_blank_lines=False, encoding="UTF-8"
    )
    # Drop all empty columns
    base_df.dropna(how="all", axis="columns", inplace=True)
    merge_df.dropna(how="all", axis="columns", inplace=True)
    # Number the gongans: blank lines denote start of new gongan. Then delete blank lines.
    base_df["gongannr"] = base_df["tag"].isna().cumsum()[~base_df["tag"].isna()] + 1
    merge_df["gongannr"] = merge_df["tag"].isna().cumsum()[~merge_df["tag"].isna()] + 1
    merge_df = merge_df[~merge_df["tag"].isin(["gangsa p", "gangsa s"])]
    # Drop all empty rows
    base_df.dropna(how="all", axis="rows", inplace=True)
    merge_df.dropna(how="all", axis="rows", inplace=True)
    # Concatenate both tables
    new_df = pd.concat([base_df, merge_df], ignore_index=True)
    # Sort the new table
    new_df["tagid"] = new_df["tag"].apply(lambda tag: sortingorder.index(tag))
    new_df.sort_values(by=["gongannr", "tagid"], inplace=True, ignore_index=True)
    # Add empty lines between gongans
    mask = new_df["gongannr"].ne(new_df["gongannr"].shift(-1))
    empties = pd.DataFrame("", index=mask.index[mask] + 0.5, columns=new_df.columns)
    new_df = pd.concat([new_df, empties]).sort_index().reset_index(drop=True).iloc[:-1]
    # Drop gongannr and tagid columns
    new_df.drop(["gongannr", "tagid"], axis="columns", inplace=True)
    new_df.to_csv(path.join(datapath, resultfile), sep="\t", index=False, header=False)


def rename_files(folderpath: str, filter: str, findtext: str, replacetext: str, print_only: bool = True):
    filelist = glob(path.join(folderpath, filter))
    if isinstance(findtext, str) and isinstance(replacetext, str):
        findtext = [findtext]
        replacetext = [replacetext]
    for filename in filelist:
        newfilename = filename
        for pos, find in enumerate(findtext):
            newfilename = newfilename.replace(find, replacetext[pos])
            if newfilename != filename:
                break
        if print_only:
            logger.info(f"{os.path.basename(filename)} -> {os.path.basename(newfilename)}")
        else:
            os.rename(filename, newfilename)
    if print_only:
        logger.info("No files were renamed (print_only==True)")


def rename_notes_in_filenames(folderpath: str, group: InstrumentGroup, print_only: bool = True):
    # In the filenames of Bali Gamelan Samples, Ding 1 is always the first note in an instrument's range.
    # This function renames the files according to the (relative) naming in this application.
    instrdict = {
        "Kantil": InstrumentType.KANTILAN,
        "Pemade": InstrumentType.PEMADE,
        "Rejong": InstrumentType.REYONG,
        "Ugal": InstrumentType.UGAL,
    }
    filenotes = sum([[f"Ding {i}", f"Dong {i}", f"Deng {i}", f"Dung {i}", f"Dang {i}"] for i in range(1, 4)], [])
    lookup = {
        instrtype: [
            pitch
            for position in Position
            if position.instrumenttype == instrtype
            for (pitch, octave, stroke) in Note.get_all_p_o_s(position)
            if octave and stroke == Stroke.OPEN
        ]
        for instrtype in instrdict.values()
    }
    for instr_name, instr_type in instrdict.items():
        notedict = {filenotes[lookup[instr_type].index(note)]: note.value for note in lookup[instr_type]}
        rename_files(
            folderpath,
            filter=f"*{instr_name}*.wav",
            findtext=list(notedict.keys()),
            replacetext=list(notedict.values()),
            print_only=print_only,
        )


def convert_to_wav_pcm(filepath_in: str, filepath_out: str):
    rate, data = wavfile.read(filepath_in)
    data = data.astype("int16")
    wavfile.write(filepath_out, rate, data)


def parse_metadata(meta: str):
    from src.common.metadata_classes import MetaDataType

    meta = meta.strip()
    membertypes = MetaDataType.__dict__["__args__"]
    # create a dict containing the valid parameters for each metadata keyword.
    # Format: {<meta-keyword>: [<parameter1>, <parameter2>, ...]}
    field_dict = {
        member.model_fields["metatype"].annotation.__args__[0]: [
            param for param in list(member.model_fields.keys()) if param not in "metatype"
        ]
        for member in membertypes
    }
    # Try to retrieve the keyword
    keyword_pattern = r"{ *([A-Z]+)"
    match = regex.match(keyword_pattern, meta)
    if not match:
        raise Exception("Could not determine metadata type.")
    meta_keyword = match.group(1)
    # Try to retrieve the corresponding fields
    fields = field_dict.get(meta_keyword, None)
    if not fields:
        raise Exception(f"Invalid keyword {meta_keyword}.")

    # Create a match pattern for the parameter values
    value_pattern_list = [
        r"(?P<value>[^,\"'\[\]]+)",  # simple unquoted value
        r"'(?P<value>[^']+)'",  # quoted value (single quotes)
        r"\"(?P<value>[^\"]+)\"",  # quoted value (double quotes)
        r"(?P<value>\[[^\[\]]+\])",  # list
    ]
    value_pattern = "(?:" + "|".join(value_pattern_list) + ")"

    # Create a pattern to validate the general format of the string, without validating the parameter nammes.
    # This test is performed separately in order to have a more specific error handling.
    single_param_pattern = r"(?: *(?P<parameter>[\w]+) *= *" + value_pattern + " *)"
    multiple_params_pattern = "(?:" + single_param_pattern + ", *)*" + single_param_pattern
    full_metadata_pattern = r"^\{ *" + meta_keyword + " +" + multiple_params_pattern + r"\}"
    # Validate the general structure (accept any parameter name)
    match = regex.fullmatch(full_metadata_pattern, meta)
    if not match:
        raise Exception("Invalid metadata format. Are the parameters separated by commas?")

    # Create a pattern requiring valid parameter nammes exclusively.
    single_param_pattern = f"(?: *(?P<parameter>{'|'.join(fields)})" + r" *= *" + value_pattern + " *)"
    multiple_params_pattern = "(?:" + single_param_pattern + ", *)*" + single_param_pattern
    full_metadata_pattern = r"^\{ *" + meta_keyword + " +" + multiple_params_pattern + r"\}"
    # Validate the parameter names.
    match = regex.fullmatch(full_metadata_pattern, meta)
    if not match:
        raise Exception(
            f"The metadata contains illegal patterns for {meta_keyword}. Valid values are {', '.join(field_dict[fields])}."
        )

    # Capture the fieldname, value pairs
    groups = [match.captures(i) for i, reg in enumerate(match.regs) if i > 0 and reg != (-1, -1)]

    # Quote non=numeric values
    nonnumeric = r'"([^"]+)"|(\w*[A-Za-z_ ]\w*\b)'
    pv = regex.compile(nonnumeric)

    # create a json string
    parameters = [f'"{p}": {pv.sub(r'"\1\2"', v)}' for p, v in zip(*groups)]
    str = f'{{"metatype": "{meta_keyword}", {" ,".join(parameters)}}}'

    return json.loads(str)


if __name__ == "__main__":
    note = Note(
        position=Position.KANTILAN_POLOS,
        symbol="a",
        pitch=Pitch.DANG,
        octave=1,
        stroke=Stroke.OPEN,
        duration=1,
        rest_after=0,
        modifier=Modifier.NONE,
    )
    note = Note(
        position=Position.KANTILAN_POLOS,
        symbol="a,",
        pitch=Pitch.DANG,
        octave=0,
        stroke=Stroke.OPEN,
        duration=1,
        rest_after=0,
        modifier=Modifier.NONE,
    )
