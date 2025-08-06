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
    "input_filename_pattern",
    "beat_at_end",
    "autocorrect_kempyung",
    "include_in_run_types",
    "include_in_production_run",
]


def update_all_folder_settings(data_folder: str):
    """updates settings.yaml for each folder in the given data_folder"""
    notations = {os.path.basename(p): p for p in glob.glob(data_folder + "/*")}

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

        # input_full = next((f for f in valid_inputfiles if "[FULL]" in f), None)
        # settings["input_filename_pattern"] = input_full.replace("[FULL]", r"[{part}]")
        # settings["loop"] = [part for part in list(part_count.keys()) if part != "FULL"]
        settings["parts"] = [part for part in list(part_count.keys())]

        # Sort the keys
        settings = {key: settings[key] for key in ordered_fields}

        with open(n_path + "/settings.yaml", "w", encoding="utf-8") as outfile:
            yaml.dump(settings, outfile, default_flow_style=False, sort_keys=False)


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
    rename_all()
    # update_all_folder_settings("./data/notation")
    # create_integration_test_settings("./data/notation", "./tests/data/notation/_integration_test/notations")
