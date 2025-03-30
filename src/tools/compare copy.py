"""
Compares MIDI files contained in two folders and outputs the differences in a file. Only files with the same name are
compared. The comparison is performed by first creating a text (.txt) version of all .mid files which contains a
readable version of the MIDI messages, and then comparing these text files.
The output is stored in the first of the two folders.
"""

import copy
import difflib
import filecmp
import json
import os
import re
from collections import defaultdict
from glob import glob
from io import TextIOWrapper
from typing import Any

from src.common.logger import get_logger
from src.tools.print_midi_file import to_text, to_text_multiple_files

LOGGER = get_logger(__name__)

META = "MetaMessage"
# Metadata attributes
TYPE = "type"
NAME = "name"
CHANNEL = "channel"
NOTE = "note"
VELOCITY = "velocity"
TIME = "time"
ABSTIME = "abstime"
TEXT = "text"
TEMPO = "tempo"
PORT = "port"
OCTAVE = "octave"
TIMEUNTIL = "timeuntil"
ISLAST = "islast"
POSITION = "position"
PITCH = "pitch"
# ID values at beginning of line
ABSTIME_ID = "abstime"  # Not used
BEAT_ID = "beat_id"
POSITION_ID = "position_id"
# Type values
MARKER = "marker"
NOTEON = "note_on"
NOTEOFF = "note_off"
TRACK_NAME = "track_name"
SET_TEMPO = "set_tempo"
MIDI_PORT = "midi_port"
END_OF_TRACK = "end_of_track"
HELPINGHAND = "helpinghand"
TYPES = [META, NOTEON, NOTEOFF]
# Summary entries
ID = "id"
SCORE = "score"
DIFF = "diff"
MATCH = "match"
NOMATCH = "nomatch"
COUNT = "count"
DETAILS = "details"


def sorted_dict(unsorted: dict[str, Any]) -> dict[str, Any]:
    """Returns the dict with sorted keys"""
    sorted_keys = sorted(list(unsorted.keys()))
    return {key: unsorted[key] for key in sorted_keys}


def attr(line: str):
    match = re.findall(r"(MetaMessage)|(note_on)|(note_off)", line)
    type_: str = next((m for m in match[0] if m), None)
    params = []
    if type_.startswith("note"):
        matcher = re.match(
            r" *\((?P<abstime>\d+),(?P<beat_id>\d+-\d+),(?P<position_id>\w*)\)[ -]+(?P<type>note_[a-z]{2,3}) channel=(?P<channel>[^ ]+) note=(?P<note>[^ ]+) velocity=(?P<velocity>[^ ]+) time=(?P<time>\d+) abstime=\d* *$",
            line,
        )
        params = matcher.groupdict() if matcher else {}
    else:
        # Metamessage. Determine type and set match string accordingly
        matcher = re.match(
            r" *\((?P<abstime>\d+),(?P<beat_id>\d+-\d+),(?P<position_id>\w*)\)[ -]+MetaMessage\('(?P<type>\w+)'(, text='(?P<text>[^']+)'|, name='(?P<name>\w+)'|, tempo=(?P<tempo>\d+)|, port=(?P<port>\d+)){0,1}, time=(?P<time>\d+)\) abstime=\d* *$",
            # r" *MetaMessage\('(?P<type>\w+)', time=(?P<time>\d+)\)[ -]+(?P<abstime>\d+)$",
            line,
        )
        params = matcher.groupdict() if matcher else {}
        params = {key: val for key, val in params.items() if val is not None}
        if params[TYPE] == MARKER:
            if HELPINGHAND in params[TEXT]:
                params[TYPE] = HELPINGHAND
                hh_params = json.loads(params[TEXT])
                del params[TEXT]
                params |= hh_params
            else:
                raise ValueError("Unexpected text value for marker, text=%s" % params[TEXT])
    return params


def eval_diff(params1: dict[str, str], params2: dict[str, str]) -> tuple[float, dict[str, str]]:
    """Calculates a similarity score for MIDI message parameters between 0 (not similar) and 1 (identical)
    and returns this score together with a dict of differing message attributes"""

    def time_diff_sanction(time1, time2) -> float:
        threshold = 30  # 30 ms is acceptable because it is imperceptible
        return 0 if abs(int(time1) - int(time2)) <= threshold else abs(int(time1) - int(time2)) - threshold

    ignore = [BEAT_ID, POSITION_ID]
    score = 0
    diff = {
        key: (val, params2.get(key, None))
        for key, val in params1.items()
        if params2.get(key, None) != val and key not in ignore
    }
    if params1[TYPE] != params2[TYPE]:
        pass  # score=0
    elif params1[TYPE] in [NOTEON, NOTEOFF]:
        # attributes: channel, note, velocity, time, abstime
        if any(key in diff for key in [CHANNEL]):
            pass  # score=0
        else:
            score = 1 - 0.1 * sum([params1[key] != params2[key] for key in [NOTE, VELOCITY, TIME, ABSTIME]])
    elif params1[TYPE] == HELPINGHAND:
        # attributes in text: position, channel, pitch, octave, timeuntil, islast
        if any(params1[key] != params2[key] for key in [POSITION, CHANNEL]):
            pass  # score=0
        else:
            diff |= {
                key: (params1[key], params2[key]) for key in [OCTAVE, TIMEUNTIL, ISLAST] if params1[key] != params2[key]
            }
            score = max(
                0,
                1
                - 0.1 * (params1[OCTAVE] != params2[OCTAVE])
                - 0.2 * time_diff_sanction(params1[TIMEUNTIL], params2[TIMEUNTIL]),
            )
    elif params1[TYPE] == SET_TEMPO:
        if params1[TEMPO] != params2[TEMPO]:
            pass  # score=0
        else:
            score = 1
    elif params1[TYPE] == MIDI_PORT:
        if params1[PORT] != params2[PORT]:
            pass  # score = 0
        else:
            score = 1
    elif params1[TYPE] == END_OF_TRACK:
        score = 1
    else:
        raise ValueError("Unexpected text value for marker %s" % params1[TYPE])

    score = max(0, score - time_diff_sanction(params1[ABSTIME], params2[ABSTIME]))
    return score, diff


def find_best_match(line: str, compare: list[str]):
    threshold = 0
    best = {ID: None, SCORE: -1, DIFF: None}
    for id, other in enumerate(compare):
        params1 = attr(line)
        params2 = attr(other)
        score, diff = eval_diff(params1, params2)
        if score > threshold > best[SCORE]:
            best = {ID: id, SCORE: score, DIFF: diff}
    return best


def summarize(compare) -> dict[str, dict[str, Any]]:

    def json_key(key: tuple[str]) -> str:
        return str(key)

    summary = defaultdict(lambda: {COUNT: 0, DETAILS: []})
    # compare_group = defaultdict(dict)
    for c_id, (_, old, new) in enumerate(compare):
        for o_id, (line, (matchid, score, nonmatches)) in enumerate(old):
            attributes = attr(line)
            type_ = attributes[TYPE]
            if score == 1:
                key = json_key(key=(MATCH, type_))
            if matchid is None:
                if type_ == HELPINGHAND:
                    type_ += " " + attributes[POSITION]
                key = json_key(key=(NOMATCH, type_))
                summary[key][COUNT] += 1
                summary[key][DETAILS].append([line, None, [it[0] for it in new]])
            else:
                key = json_key(key=(DIFF, attr(line)[TYPE], *tuple(nonmatches.keys())))
                summary[key][COUNT] += 1
                summary[key][DETAILS].append([line, new[matchid], [it[0] for it in new]])
            # compare_group[c_id][o_id] = key
    if not summary:
        summary = {"No differences": {COUNT: "-", DETAILS: {}}}
    return sorted_dict(summary)


def compare_file_contents(file1: str, file2: str) -> dict[int, dict[int, tuple[str]]]:
    """Compares two files and returns the differences in a unified diff format.
    Args:
        file1, file2 (_type_): path to the files
    Returns:
        str: The differences.
    """
    with open(file1, "r", encoding="utf-8") as f1, open(file2, "r", encoding="utf-8") as f2:
        # Remove additional marker messages that are added to the test output for easier location of differences
        f1_lines = [
            line
            for line in f1.readlines()
            if not "MetaMessage('marker', text='b_" in line and any(t in line for t in TYPES)
        ]
        f2_lines = [
            line
            for line in f2.readlines()
            if not "MetaMessage('marker', text='b_" in line and any(t in line for t in TYPES)
        ]
    matcher = difflib.SequenceMatcher(
        None,
        [re.sub(r"time=\d+", "", l.split(" -- ")[1]) for l in f1_lines],
        [re.sub(r"time=\d+", "", l.split(" -- ")[1]) for l in f2_lines],
    )
    opcodes = matcher.get_opcodes()
    opcodes = [code for code in opcodes if code[0] != "equal"]
    opcodes = [[c[0], f1_lines[c[1] : c[2]], f2_lines[c[3] : c[4]]] for c in opcodes]
    compare = copy.deepcopy(opcodes)
    for groupid, (_, old, new) in enumerate(opcodes):
        for nn, line_n in enumerate(new):
            # best_matches = difflib.get_close_matches(line_n, old, n=1)
            # best_match = best_matches[0] if best_matches else None
            # ratio = difflib.SequenceMatcher(None, line_n, best_match).ratio()
            # no = next((nr for nr, line_o in enumerate(old) if line_o == best_match), None)
            # mismatch_o = eval_match(old[no], line_n) if no else None
            # mismatch_n = eval_match(line_n, old[no]) if no else None
            best_match = find_best_match(line_n, old)
            if (no := best_match[ID]) is not None and best_match[SCORE] < 1:
                compare[groupid][1][no] = [opcodes[groupid][1][no], (nn, best_match[SCORE], best_match[DIFF])]
            compare[groupid][2][nn] = [opcodes[groupid][2][nn], (no, best_match[SCORE], best_match[DIFF])]

        for no, line in enumerate(compare[groupid][1]):
            if isinstance(line, str):
                compare[groupid][1][no] = [compare[groupid][1][no], (None, 0, None)]

    summary = summarize(compare)
    return summary


def compare_directories(dir1: str, dir2: str, file_filter="*.txt"):
    """Compares all files with the same name in two folders.
    Args:
        dir1, dir2 (str): _description_
        dir2 (_type_): _description_
        file_filter (str, optional): Defaults to "*.txt".

    Returns:
        _type_: _description_
    """
    dir1_files = glob(os.path.join(dir1, file_filter))
    dir2_files = glob(os.path.join(dir2, file_filter))

    common_files = set(os.path.basename(f) for f in dir1_files).intersection(
        set(os.path.basename(f) for f in dir2_files)
    )

    differences = {}
    for file in common_files:
        LOGGER.info(f"Comparing {file}")

        file1 = os.path.join(dir1, file)
        file2 = os.path.join(dir2, file)

        if not filecmp.cmp(file1, file2, shallow=False):
            differences[file] = compare_file_contents(file1, file2)
        else:
            differences[file] = {"No differences": {COUNT: "-", DETAILS: {}}}

    return sorted_dict(differences)


def save_file_summary(stream: TextIOWrapper, summary: dict[str, dict[str, str]], detailed: bool) -> None:
    tab0 = " " * 5
    tab1 = " " * 10
    tab2 = tab1 + "  - "
    tab3a = tab1 + "  > "
    tab3b = tab1 + "    "
    for key, value in summary.items():
        stream.write(tab0 + f"{key}: {value[COUNT]}\n")
        if detailed:
            for item in value[DETAILS]:
                if item[1]:
                    stream.write(tab1 + json.dumps(item[1][1][2]) + "\n")
                else:
                    stream.write("")
                stream.write(tab2 + f"{item[0].strip()}\n")
                if item[1]:
                    stream.write(tab3a + f"{item[1][0].strip()}\n")
                else:
                    for nr, line in enumerate(item[2]):
                        stream.write(f"{tab3a if nr==0 else tab3b}{line.strip()}\n")
                # stream.write("\n")


def compare_txt_files(
    filepath_old: str,
    filepath_new: str,
):
    """Compares two files. Result is stored in filename_out in the folder containing filepath_new
    Args:
        folderpath: (str): path containing the files
        filepath_old (str): First folder
        filepath_new (str): Second folder
    """
    # compare the text files
    if not filecmp.cmp(filepath_old, filepath_new, shallow=False):
        differences = compare_file_contents(filepath_old, filepath_new)
    else:
        differences = {"No differences": {COUNT: "-", DETAILS: {}}}

    # save report to file
    filepath_out = os.path.split(filepath_new)[0]
    with open(os.path.join(filepath_out, "comparison.txt"), "w", encoding="utf-8") as outfile:
        outfile.write(os.path.split(filepath_old)[1] + "\n")
        save_file_summary(outfile, summary=differences, detailed=False)
    with open(os.path.join(filepath_out, "comparison_details.txt"), "w", encoding="utf-8") as outfile:
        outfile.write(os.path.split(filepath_old)[1] + "\n")
        save_file_summary(outfile, summary=differences, detailed=False)


def compare_all(ref_dir: str, other_dir: str):
    """Compares all matching midi files in two directories
       or compares two files.
    Args:
        dir_old (_type_): First folder
        dir_new (_type_): Second folder
    """
    # 1. convert midi files to text files
    LOGGER.info("Generating .TXT versions of each MIDI file")
    files = []
    for folder in [ref_dir, other_dir]:
        files.append(set([os.path.basename(path) for path in glob(os.path.join(folder, "*.mid"))]))
    filelist = files[0].intersection(files[1])
    to_text_multiple_files(filelist, [ref_dir, other_dir])
    # to_text_multiple_files(filelist, [dir_new])

    # 2. compare the text files
    LOGGER.info("Generating differences report")
    differences = compare_directories(ref_dir, other_dir, "*.txt")

    # 3. save report to file
    with open(os.path.join(other_dir, "comparison.txt"), "w", encoding="utf-8") as outfile:
        for file, diff in differences.items():
            outfile.write(f"Differences in {file}:\n")
            save_file_summary(outfile, summary=diff, detailed=False)
    with open(os.path.join(other_dir, "comparison_details.txt"), "w", encoding="utf-8") as outfile:
        for file, diff in differences.items():
            outfile.write(f"Differences in {file}:\n")
            save_file_summary(outfile, summary=diff, detailed=True)


if __name__ == "__main__":
    REF_DIR = "./tests/data/notation/_integration_test/reference"
    OTHER_DIR = "./tests/data/notation/_integration_test/output"
    RUNALL = True
    if RUNALL:
        compare_all(REF_DIR, OTHER_DIR)
    else:
        FILENAME = "Cendrawasih_full_GAMELAN1.txt"
        compare_txt_files(os.path.join(REF_DIR, FILENAME), os.path.join(OTHER_DIR, FILENAME))
