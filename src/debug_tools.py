from glob import glob
from os import path
from pprint import pprint

import pandas as pd

from notation_classes import Character, InstrumentTag, MidiNote
from notation_to_midi import Source
from src.notation_constants import InstrumentPosition, InstrumentType


def get_all_tags():
    folder = "G:\\Marc\\documents-backup-2jun24-08h00\\Documents\\administratie\\_VRIJETIJD_REIZEN\\Gamelangroepen\\Studiemateriaal\\Muzieknotatie"
    files = [file for file in glob(path.join(folder, "*.xlsx")) if not path.basename(file).startswith("_")]
    tagdict = dict()
    for file in files:
        taglist = set(pd.read_excel(file).iloc[:, 0].unique())
        tagdict.update({tag: path.basename(file) for tag in taglist if isinstance(tag, str)})
    pprint(sorted(list(tagdict.keys())))
    pprint(tagdict)


d = {
    "GO": {"GONGS"},
    "KE": {"KEMPLI"},
    "CE": {"CENGCENG"},
    "KE": {"KENDANG"},
    "JE": {"JEGOGAN"},
    "CA": {"CALUNG"},
    "PEN": {"PENYACAH"},
    "PEM": {"PEMADE"},
    "KAN": {"KANTILAN"},
    "UG": {"UGAL"},
    "GA": {"PEMADE", "KANTILAN"},
    "GE": {"GENDERRAMBAT"},
    "GY": {"UGAL"},
    "RE": {"REYONG"},
    "TR": {"TROMPONG"},
}


def lookup(value: str):
    tags = d.get(value.upper()[:3], d.get(value.upper()[:2], set())).copy()
    for sep in "/,+":
        vals = value.split(sep)
        for val in vals:
            tags.update(d.get(val.strip().upper()[:3], d.get(val.strip().upper()[:2], set())).copy())
    return list(tags)


def generate_instrumenttags():
    tags_df = pd.read_csv("./settings/instrumenttags_1.csv", sep="\t")
    tags_df["instruments"] = tags_df.tag.apply(lookup)
    tags_df.to_csv("./settings/instrumenttags.csv", sep="\t", index=False)


def map_positions():
    instrumenttag_dict = pd.read_csv("./settings/instrumenttags_1.csv", sep="\t").to_dict(orient="records")
    tag0 = InstrumentTag.model_validate(instrumenttag_dict[0])
    tags = [InstrumentTag.model_validate(tag) for tag in instrumenttag_dict]
    mapping_r = [
        (
            ["reyong13", "reyong1+3", "reyong 1/3", "reyong p"],
            [InstrumentPosition.REYONG_1, InstrumentPosition.REYONG_3],
        ),
        (
            ["reyong24", "reyong2+4", "reyong 2.4", "reyong s", "reyong 2/4"],
            [InstrumentPosition.REYONG_2, InstrumentPosition.REYONG_4],
        ),
        (["reyong12", "reyong1+2"], [InstrumentPosition.REYONG_1, InstrumentPosition.REYONG_2]),
        (["reyong34", "reyong3+4"], [InstrumentPosition.REYONG_3, InstrumentPosition.REYONG_4]),
        (["reyong1-3"], [InstrumentPosition.REYONG_1, InstrumentPosition.REYONG_3]),
        (["reyong2-4"], [InstrumentPosition.REYONG_2, InstrumentPosition.REYONG_4]),
        (
            ["reyong1-4"],
            [
                InstrumentPosition.REYONG_1,
                InstrumentPosition.REYONG_2,
                InstrumentPosition.REYONG_3,
                InstrumentPosition.REYONG_4,
            ],
        ),
        (["reyong1", "reyong(1)", "reyong 1"], [InstrumentPosition.REYONG_1]),
        (["reyong2", "reyong(2)", "reyong 2"], [InstrumentPosition.REYONG_2]),
        (["reyong3", "reyong(3)", "reyong 3"], [InstrumentPosition.REYONG_3]),
        (["reyong4", "reyong(4)", "reyong 4"], [InstrumentPosition.REYONG_4]),
        (
            ["Reyong", "reyong", "rey/", "/rey", "+rey"],
            [
                InstrumentPosition.REYONG_1,
                InstrumentPosition.REYONG_2,
                InstrumentPosition.REYONG_3,
                InstrumentPosition.REYONG_4,
            ],
        ),
    ]
    mapping_g = [
        (
            ["gangsa p/s"],
            [
                InstrumentPosition.PEMADE_POLOS,
                InstrumentPosition.PEMADE_SANGSIH,
                InstrumentPosition.KANTILAN_POLOS,
                InstrumentPosition.KANTILAN_SANGSIH,
            ],
        ),
        (["gangsa p", "gang p", "ga p", "/ga.p"], [InstrumentPosition.PEMADE_POLOS, InstrumentPosition.KANTILAN_POLOS]),
        (["gangsa s", "ga s"], [InstrumentPosition.PEMADE_SANGSIH, InstrumentPosition.KANTILAN_SANGSIH]),
        (["pemade p"], [InstrumentPosition.PEMADE_POLOS]),
        (["pemade s"], [InstrumentPosition.PEMADE_SANGSIH]),
        (["kantilan p"], [InstrumentPosition.KANTILAN_POLOS]),
        (["kantilan s"], [InstrumentPosition.KANTILAN_SANGSIH]),
        (["pemade"], [InstrumentPosition.PEMADE_POLOS, InstrumentPosition.PEMADE_SANGSIH]),
        (["kantilan"], [InstrumentPosition.KANTILAN_POLOS, InstrumentPosition.KANTILAN_SANGSIH]),
        (
            ["ga ", "ga+", "ga/", "/ga", "/gang", "gang.", "ga4", "gangs4", "gangsa", "(ga)", "/ ga"],
            [
                InstrumentPosition.PEMADE_POLOS,
                InstrumentPosition.PEMADE_SANGSIH,
                InstrumentPosition.KANTILAN_POLOS,
                InstrumentPosition.KANTILAN_SANGSIH,
            ],
        ),
    ]
    for mytag in tags:
        mytag.positions = [
            InstrumentPosition[instr.value] for instr in mytag.instruments if instr.value in InstrumentPosition
        ]
        for values, positions in mapping_r:
            if any(val in mytag.tag for val in values):
                mytag.positions.extend(positions)
                break
        for values, positions in mapping_g:
            if any(val in mytag.tag for val in values):
                mytag.positions.extend(positions)
                break
    tags_dict = [mytag.model_dump() for mytag in tags]
    print([t.tag for t in tags if not t.positions])
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
    # Number the systems: blank lines denote start of new system. Then delete blank lines.
    base_df["sysnr"] = base_df["tag"].isna().cumsum()[~base_df["tag"].isna()] + 1
    merge_df["sysnr"] = merge_df["tag"].isna().cumsum()[~merge_df["tag"].isna()] + 1
    merge_df = merge_df[~merge_df["tag"].isin(["gangsa p", "gangsa s"])]
    # Drop all empty rows
    base_df.dropna(how="all", axis="rows", inplace=True)
    merge_df.dropna(how="all", axis="rows", inplace=True)
    # Concatenate both tables
    new_df = pd.concat([base_df, merge_df], ignore_index=True)
    # Sort the new table
    new_df["tagid"] = new_df["tag"].apply(lambda tag: sortingorder.index(tag))
    new_df.sort_values(by=["sysnr", "tagid"], inplace=True, ignore_index=True)
    # Add empty lines between systems
    mask = new_df["sysnr"].ne(new_df["sysnr"].shift(-1))
    empties = pd.DataFrame("", index=mask.index[mask] + 0.5, columns=new_df.columns)
    new_df = pd.concat([new_df, empties]).sort_index().reset_index(drop=True).iloc[:-1]
    # Drop sysnr and tagid columns
    new_df.drop(["sysnr", "tagid"], axis="columns", inplace=True)
    new_df.to_csv(path.join(datapath, resultfile), sep="\t", index=False, header=False)


CENDRAWASIH = Source(
    datapath=".\\data\\cendrawasih", infilename="Cendrawasih.csv", outfilefmt="Cendrawasih {position}.mid"
)
if __name__ == "__main__":
    merge_parts(CENDRAWASIH.datapath, CENDRAWASIH.infilename, "overige_instrumenten.csv", "Cendrawasih_complete.csv")
