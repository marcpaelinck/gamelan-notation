import glob
import os
import re
import shutil

import yaml

ordered_fields = [
    "title",
    "instrumentgroup",
    "fontversion",
    "parts",
    "loop",
    "beat_at_end",
    "run_types",
]


def update_all_folder_settings(data_folder: str):
    """updates settings.yaml for each folder in the given data_folder"""
    notations = {os.path.basename(p): p for p in glob.glob(data_folder + "/*") if os.path.isdir(p)}

    for notation, n_path in notations.items():
        if not os.path.exists(n_path + "/settings.yaml"):
            continue
        shutil.copy(n_path + "/settings.yaml", data_folder + "/" + notation + ".yaml")
        with open(n_path + "/settings.yaml", "r", encoding="utf-8") as infile:
            settings = yaml.safe_load(infile)

        inputfiles = [os.path.basename(p) for p in glob.glob(n_path + "/*.tsv")]
        parts = []
        valid_inputfiles = []
        for inputfile in inputfiles:
            matcher = re.match(r"[\w ]+_\[(?P<part>[A-Z]+)\].tsv", inputfile)
            if matcher:
                parts.append(matcher.groupdict()["part"].upper())
                valid_inputfiles.append(inputfile)

        if not valid_inputfiles:
            continue

        part_count = {part: len([p for p in parts if p == part]) for part in set(parts)}
        duplicates = [key for key, val in part_count.items() if val > 1]
        if duplicates:
            print(f"{notation} had duplicates: {','.join(duplicates)}")
            continue

        settings["parts"] = [part for part in list(part_count.keys())]

        # Sort the keys
        settings = {key: settings[key] for key in ordered_fields}

        with open(n_path + "/settings.yaml", "w", encoding="utf-8") as outfile:
            yaml.dump(settings, outfile, default_flow_style=False, sort_keys=False)


def add_info_to_notations(data_folder: str):
    """adds an INFO metadata to the beginning of each notation file"""
    # Collect all notation files having a part indicator in the name and not containing the word 'skip'
    notation_dict = {}

    def n(key: str):
        value = notation_dict.get(key, None)
        if isinstance(value, str) and " " in value:
            value = '"' + value + '"'
        if isinstance(value, bool):
            value = str(value).lower()
        return value

    fmt = (
        "{{INFO notation={notation} part={part} "
        "title={title} instrumentgroup={instrumentgroup} "
        "font={font} runtypes={runtypes} "
        "loop={loop} beat_at_end={beat_at_end}}}"
    )

    matchpart = re.compile(r"\[(?P<part>[\w ]+)\]")
    notations = {
        os.path.basename(folder): [
            path
            for path in glob.glob(folder + "/*.tsv")
            if not ("skip" in path) and not ("_OLD" in path) and matchpart.search(path)
        ]
        for folder in glob.glob(data_folder + "/*")
        if os.path.isdir(folder)
    }
    # Create a list of records containing the notation and part information and file path.
    notations = [
        {"notation": folder, "part": matchpart.search(path).group("part"), "path": path}
        for folder, paths in notations.items()
        for path in paths
    ]

    defaults = {"runtypes": ["DEBUG", "PRODUCTION"], "loop": False, "beat_at_end": False}
    for notation_dict in notations:
        shutil.copy(notation_dict["path"].replace(".tsv", "_OLD.tsv"), notation_dict["path"])
        with open(os.path.dirname(notation_dict["path"]) + "/settings.yaml", "r", encoding="utf-8") as settingsfile:
            settings = yaml.safe_load(settingsfile)
        notation_dict |= defaults | settings
        with open(notation_dict["path"], "r", encoding="utf-8") as notationfile:
            notation_content = notationfile.read()
        notation_content = (
            fmt.format(
                notation=n("notation"),
                part=n("part"),
                title=n("title"),
                instrumentgroup=n("instrumentgroup"),
                font=n("fontversion"),
                runtypes=n("runtypes"),
                loop="false" if n("part") == "full" else "true",
                beat_at_end=n("beat_at_end"),
            )
            + "\n"
            + notation_content
        )
        with open(notation_dict["path"], "w", encoding="utf-8") as notationfile:
            notation_content = notationfile.write(notation_content)

        print(
            fmt.format(
                notation=n("notation"),
                part=n("part"),
                title=n("title"),
                instrumentgroup=n("instrumentgroup"),
                font=n("fontversion"),
                runtypes=n("runtypes"),
                loop="false" if n("part") == "full" else "true",
                beat_at_end=n("beat_at_end"),
            )
        )

    x = 1


def create_integration_test_settings(data_folder: str, unittest_folder: str):
    notations = {os.path.basename(p): p for p in glob.glob(data_folder + "/*")}
    settings = {}

    for notation, n_path in notations.items():
        if not os.path.exists(n_path + "/settings.yaml"):
            continue
        with open(n_path + "/settings.yaml", "r", encoding="utf-8") as infile:
            folder_settings = yaml.safe_load(infile)
        settings[notation] = folder_settings

    with open(unittest_folder + "/settings_new.yaml", "w", encoding="utf-8") as outfile:
        yaml.dump(settings, outfile, default_flow_style=False, sort_keys=False)


def rename_all():
    old_new = [
        ("Bapang Selisir_full_GAMELAN1.mid", "Bapang Selisir SP_[FULL]_GAMELAN1.mid"),
        ("Cendrawasih_full_GAMELAN1.mid", "Cendrawasih_complete_[FULL]_GAMELAN1.mid"),
        ("Gilak Deng_full_GAMELAN1.mid", "Gilak Deng_[FULL]_GAMELAN1.mid"),
        ("Godek Miring_full_GAMELAN1.mid", "Godek Miring SP_[FULL]_GAMELAN1.mid"),
        ("Janger_full_GAMELAN1.mid", "Janger_[FULL]_GAMELAN1.mid"),
        ("Kahyangan_full_GAMELAN1.mid", "Kahayangan_[FULL]_GAMELAN1.mid"),
        ("Legong Mahawidya_full_GAMELAN1.mid", "Legong Mahawidya GK_[FULL]_GAMELAN1.mid"),
        ("Lengker_full_GAMELAN1.mid", "Lengker Ubud SP_[FULL]_GAMELAN1.mid"),
        ("Margapati_full_GAMELAN1.mid", "Margapati_[FULL]_GAMELAN1.mid"),
        ("Pendet_full_GAMELAN1.mid", "pendet_beat_at_end_[FULL]_GAMELAN1.mid"),
        ("Puspa Mekar_full_GAMELAN1.mid", "Puspa Mekar_[FULL]_GAMELAN1.mid"),
        ("Rejang Dewa_full_GAMELAN1.mid", "rejang dewa_[FULL]_GAMELAN1.mid"),
        ("Sekar Gendot_full_GAMELAN1.mid", "Sekar Gendot SP_[FULL]_GAMELAN1.mid"),
        ("Sinom Ladrang (GK)_full_GAMELAN1.mid", "Sinom Ladrang GK_ubit4_[FULL]_GAMELAN1.mid"),
        ("Sinom Ladrang_full_GAMELAN1.mid", "Sinom Ladrang SP_[FULL]_GAMELAN1.mid"),
    ]
    os.chdir("./tests/data/notation/_integration_test/reference")
    for old, new in old_new:
        os.rename(old, new)


if __name__ == "__main__":
    add_info_to_notations("./data/notation")
    # update_all_folder_settings("./data/notation")
    # create_integration_test_settings("./data/notation", "./tests/data/notation/_integration_test/notations")
