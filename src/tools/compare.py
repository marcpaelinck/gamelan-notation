"""
Compares MIDI files contained in two folders and outputs a report of the differences. Only files with the same name are
compared. The comparison is performed by first creating a text (.txt) version of all .mid files which contains a
readable version of the MIDI messages, and then comparing these text files. This makes it easier to analyse the results.
The report files are stored in the folder that is being compared to the reference folder.
"""

import difflib
import filecmp
import itertools
import json
import os
import re
from collections import defaultdict
from glob import glob
from io import TextIOWrapper
from typing import Any

from mido import MidiFile

from src.common.logger import Logging

LOGGER = Logging.get_logger(__name__)

# ID values at beginning of line
ABSTIME_ID = "abstime"  # Not used
BEAT_ID = "beat_id"
PASS_ID = "pass_id"
POSITION_ID = "position_id"
# Message types
META = "MetaMessage"
NOTEON = "note_on"
NOTEOFF = "note_off"
MESSAGETYPES = [META, NOTEON, NOTEOFF]
# Metamessage types
MARKER = "marker"
TRACK_NAME = "track_name"
SET_TEMPO = "set_tempo"
MIDI_PORT = "midi_port"
END_OF_TRACK = "end_of_track"
HELPINGHAND = "helpinghand"
# Message attributes
# In case of metamessage, TYPE is the metamessage type.
# For type 'marker' the marker type is used (currently only HELPINGHAND)
TYPE = "type"
COMPARE_TYPES = [NOTEON, NOTEOFF, TRACK_NAME, SET_TEMPO, END_OF_TRACK, HELPINGHAND]  # MIDI_PORT] <-- to be added
NAME = "name"
CHANNEL = "channel"
NOTE = "note"
PITCH = "pitch"
OCTAVE = "octave"
VELOCITY = "velocity"
TIME = "time"
ABSTIME = "abstime"
TEXT = "text"
TEMPO = "tempo"
PORT = "port"
HH_ID = "hh_id"
HH_TYPE = "hh_type"
HH_TIMEUNTIL = "hh_timeuntil"
HH_POSITION = "hh_position"
HH_CHANNEL = "hh_channel"
HH_NOTE = "hh_note"
HH_PITCH = "hh_pitch"
HH_OCTAVE = "hh_octave"
HH_ISLAST = "hh_islast"
# Match types for message attributes.
ALWAYS = "always"  # attributes should always match.
CLOSEST = "closest"  # numeric values only: find closest match. Max tolerated difference: see MIN_MAX_DIFF_DICT below.
OPTIONAL = "optional"  # attributes should preferably match.
# ATTRIBUTES_DICT contains message attributes for each (meta)type with an indication of the match type
# See function `find_best_match` for more information about match types.
# Because of the order of the match attempts, the CLOSEST values should be ordered in ascending order of preference
# and OPTIONAL values in descending order. The best_matches algorithm will try to find an exact match with a higher
# priority for attributes with a higher preference.
ATTRIBUTES_DICT = {
    NOTEON: {ALWAYS: [TYPE, POSITION_ID, CHANNEL], CLOSEST: [ABSTIME], OPTIONAL: [TIME, NOTE, VELOCITY]},
    NOTEOFF: {ALWAYS: [TYPE, POSITION_ID, CHANNEL], CLOSEST: [ABSTIME], OPTIONAL: [TIME, NOTE, VELOCITY]},
    SET_TEMPO: {ALWAYS: [TYPE, POSITION_ID], CLOSEST: [TEMPO, ABSTIME], OPTIONAL: [TIME]},
    MIDI_PORT: {ALWAYS: [TYPE, POSITION_ID, PORT, TIME], CLOSEST: [], OPTIONAL: []},
    END_OF_TRACK: {ALWAYS: [TYPE, POSITION_ID, TIME], CLOSEST: [], OPTIONAL: [TIME]},
    HELPINGHAND: {
        ALWAYS: [TYPE, POSITION_ID, TIME, HH_POSITION, HH_CHANNEL],
        CLOSEST: [HH_TIMEUNTIL, ABSTIME],
        OPTIONAL: [TIME, HH_ISLAST, HH_PITCH, HH_OCTAVE, HH_ID],
    },
}
# Settings for findinng a 'close match'.
#  Tuple value 1: the maximum difference between two value to still consider them as being equal.
#  Tuple value 2: the maximum difference between two value that should be considered as a 'close' match.
MIN_MAX_DIFF_DICT = {ABSTIME: (0, 30), TEMPO: (0, 10000), HH_TIMEUNTIL: (1, 30)}
# DICT keys of the return values of the find_best_match function
MATCH_ID = "match"
MATCH_MESSAGE = "message"
MATCH_APPROX_ATTR = "approximated"
MATCH_IGNORED_ATTR = "ignored"
# Summary entries
ID = "id"
SCORE = "score"
DIFF = "diff"
MATCH = "match"
NOMATCH_1 = "NO MATCH REF"
NOMATCH_2 = "NO MATCH NEW"
COUNT = "count"
DETAILS = "details"

NO_DIFFERENCES = {"No differences": tuple()}


def to_text(path, midifilename):
    midifilepath = os.path.join(path, midifilename)
    txtfilepath = os.path.splitext(midifilepath)[0] + ".txt"

    mid = MidiFile(midifilepath)
    beat = "00-0"
    position = "X"
    with open(txtfilepath, "w", encoding="utf-8") as csvfile:
        for i, track in enumerate(mid.tracks):
            clocktime = 0
            passes: dict[str, int] = defaultdict(lambda: 0)
            csvfile.write("Track {}: {}".format(i, track.name) + "\n")
            for msg in track:
                do_write = True
                match = re.findall(r"'marker', text='b_(\d+-\d+)'", str(msg))
                if match:
                    # This is a 'marker' metamessage which contains beat and pass information
                    # The information will be added to the following messages. The marker
                    # message itself should not be saved.
                    if match[0] != beat:
                        passes[match[0]] += 1
                    beat = match[0]
                    do_write = False
                else:
                    match = re.findall(r"'track_name', name='(\w+)'", str(msg))
                    if match:
                        # Similar to the 'marker' metamessages, this message will not be exported
                        # but the track information will be added to the following messages.
                        position = match[0]
                        do_write = False
                clocktime += msg.time
                if do_write:
                    csvfile.write(
                        f"    ({clocktime},{beat},{passes[beat]},{position}) -- {str(msg)} abstime={clocktime}" + "\n"
                    )


def to_text_multiple_files(files: list[str], folders: list[str]):
    LOGGER.log_progress("")
    for file in files:
        for folder in folders:
            LOGGER.log_progress()
            to_text(folder, file)
    LOGGER.log_final(message="")


def sorted_dict(unsorted: dict[str, Any]) -> dict[str, Any]:
    """Returns the dict with sorted keys"""
    sorted_keys = sorted(list(unsorted.keys()))
    return {key: unsorted[key] for key in sorted_keys}


def attr(line: str):
    match = re.findall(r"(MetaMessage)|(note_on)|(note_off)", line)
    type_: str = next((m for m in match[0] if m), None)
    params = []
    if type_.startswith("note"):
        # pylint: disable=line-too-long
        matcher = re.match(
            r" *\((?P<abstime>\d+),(?P<beat_id>\d+-\d+),(?P<pass_id>\d+),(?P<position_id>\w*)\)[ -]+(?P<type>note_[a-z]{2,3}) channel=(?P<channel>[^ ]+) note=(?P<note>[^ ]+) velocity=(?P<velocity>[^ ]+) time=(?P<time>\d+) abstime=\d* *$",
            line,
        )
        params = matcher.groupdict() if matcher else {}
    else:
        # Metamessage. Determine type and set match string accordingly
        matcher = re.match(
            r" *\((?P<abstime>\d+),(?P<beat_id>\d+-\d+),(?P<pass_id>\d+),(?P<position_id>\w*)\)[ -]+MetaMessage\('(?P<type>\w+)'(, text='(?P<text>[^']+)'|, name='(?P<name>\w+)'|, tempo=(?P<tempo>\d+)|, port=(?P<port>\d+)){0,1}, time=(?P<time>\d+)\) abstime=\d* *$",
            line,
        )
        # pylint: enable=line-too-long
        # Parse the message attributes
        params = matcher.groupdict() if matcher else {}
        # Remove missing values and convert any numeric type to a numeric value
        params = {key: val for key, val in params.items() if val is not None}

        if params[TYPE] == MARKER:
            if HELPINGHAND in params[TEXT]:
                # Parse the text parameter to a json object
                # This will automatically convert number-like values to numbers
                params[TYPE] = HELPINGHAND
                hh_params: dict[str, Any] = json.loads(params[TEXT])
                # Add prefix hh_ to all HelpingHand parameters and add them to the params list.
                hh_params = {"hh_" + key: val for key, val in hh_params.items()}
                hh_params[HH_TIMEUNTIL] = int(hh_params[HH_TIMEUNTIL])
                del params[TEXT]
                params |= hh_params
            else:
                raise ValueError("Unexpected text value for marker, text=%s" % params[TEXT])
    params = {
        key: eval(val) if isinstance(val, str) and bool(re.match(r"^-*\d+\.*\d*$", val)) else val
        for key, val in params.items()
    }
    return params


def find_best_match(
    message: dict[str, str | int | float], msg_list: list[dict[str, str | int | float]]
) -> tuple[int, tuple[str]]:
    """Finds the best matching message in msg_list for the given message. A message is represented
    as a dict {attribute: value}.
    This method uses the definitions in ATTRIBUTES_DICT which contains the attribute names
    of each message type, grouped in three categories:
    - ALWAYS: these attributes should always match exactly.
    - CLOSEST: (numeric values only) find closest match where the maximum deviation for each attribute
             is given in MAX_DIFF_DICT.
    - OPTIONAL: match as many of these attributes as possible.
    Args:
        message (dict[str, str  |  int  |  float]): _description_
        msg_list (list[dict[str, str  |  int  |  float]]): _description_
    Raises:
        ValueError: if an unexpected message type is encountered.
    Returns:
        tuple[int, tuple[str]]: _description_
    """
    # Find the corresponding entry in the ATTRIBUTES_DICT dictionary.
    if not message[TYPE] in ATTRIBUTES_DICT:
        raise ValueError("Unexpected message type %s" % message[TYPE])
    attributes = ATTRIBUTES_DICT[message[TYPE]]
    # create combinations of n, n-1, ... 0  OPTIONAL attributes to match.
    match_optional_combis = sum(
        [list(itertools.combinations(attributes[OPTIONAL], i)) for i in range(len(attributes[OPTIONAL]), -1, -1)], []
    )
    # create combinations of 0,..,n DELTA attributes to approximmate.
    close_match_combis = sum(
        [list(itertools.combinations(attributes[CLOSEST], i)) for i in range(0, len(attributes[CLOSEST]) + 1)], []
    )
    # Reduce the search range by filtering the message list on ABSTIME
    short_msg_list = [
        (id, msg)
        for id, msg in enumerate(msg_list)
        if abs(message[ABSTIME] - msg[ABSTIME]) < MIN_MAX_DIFF_DICT[ABSTIME][1]
    ]

    for close_match_attributes, match_optional_attributes in itertools.product(
        close_match_combis, match_optional_combis
    ):
        exact_match_attributes = set(attributes[ALWAYS]) | set(match_optional_attributes)
        # equal_close_match_attributes are 'CLOSEST' attributes that should evaluate to 'equal'.
        # See explanation of MIN_MAX_DIFF_DICT above.
        equal_close_match_attributes = set(attributes[CLOSEST]) - set(close_match_attributes)
        matches = [
            (idx, msg)
            for idx, msg in short_msg_list
            if all(msg.get(a, None) == message[a] for a in exact_match_attributes)
            and all(abs(msg.get(a, 1e8) - message[a]) <= MIN_MAX_DIFF_DICT[a][0] for a in equal_close_match_attributes)
            and all(abs(msg.get(a, 1e8) - message[a]) <= MIN_MAX_DIFF_DICT[a][1] for a in close_match_attributes)
        ]
        if matches:
            break
    best = matches[0] if matches else None

    # pylint: disable=undefined-loop-variable
    if best:
        return {
            MATCH_ID: best[0],
            MATCH_MESSAGE: best[1],
            MATCH_APPROX_ATTR: list(close_match_attributes),
            MATCH_IGNORED_ATTR: list(set(attributes[OPTIONAL]) - set(match_optional_attributes)),
        }
    # pylint: enable=undefined-loop-variable
    return None


def compare_file_contents(file1: str, file2: str) -> dict[tuple[str], tuple[dict[str, Any]], list[dict[str, Any]]]:
    """Compares two files and returns the differences in a unified diff format.
    Only the message types given in COMPARE_TYPES will be compared.
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
            if not "MetaMessage('marker', text='b_" in line and any(t in line for t in MESSAGETYPES)
        ]
        f2_lines = [
            line
            for line in f2.readlines()
            if not "MetaMessage('marker', text='b_" in line and any(t in line for t in MESSAGETYPES)
        ]
    matcher = difflib.SequenceMatcher(
        None,
        [l.split(" -- ")[1] for l in f1_lines],
        [l.split(" -- ")[1] for l in f2_lines],
    )
    opcodes = matcher.get_opcodes()
    # Remove matched lines from f1_lines and f2_lines and parse the message types and attributes
    f1_remain = [[attr(line), (c[3], c[4])] for c in opcodes if c[0] != "equal" for line in f1_lines[c[1] : c[2]]]
    f2_remain = sum([f2_lines[c[3] : c[4]] for c in opcodes if c[0] != "equal"], [])
    f2_remain = [attr(line) for line in f2_remain]

    report = defaultdict(list)

    for _, (message1, _) in enumerate(f1_remain):
        best_match = find_best_match(message1, f2_remain)
        if best_match:
            diff_group = tuple(best_match[MATCH_APPROX_ATTR] + best_match[MATCH_IGNORED_ATTR])
            if diff_group:
                # Only store partial matches
                category = ("DIFF", message1[TYPE], diff_group)
                # Mark the attributes that differ by converting the key to uppercase
                message1 = {key.upper() if key in diff_group else key: val for key, val in message1.items()}
                f2_match = {
                    key.upper() if key in diff_group else key: val for key, val in best_match[MATCH_MESSAGE].items()
                }
                report[category].append((message1, [f2_match]))
            f2_remain.pop(best_match[MATCH_ID])
        else:
            category = NOMATCH_1, message1[TYPE]
            # report[category].append((message1, f2_remain_original[f2_match_range[0] : f2_match_range[1]]))
            report[category].append((message1, []))
    if f2_remain:
        for msgtype in COMPARE_TYPES:
            msglist = [([], msg) for msg in f2_remain if msg[TYPE] == msgtype]
            if msglist:
                category = NOMATCH_2, msgtype
                report[category] = msglist

    if not report:
        report = NO_DIFFERENCES

    return sorted_dict(report)


def compare_directories(
    dir1: str, dir2: str, file_filter="*.txt"
) -> dict[str, dict[tuple[str] | str, tuple[dict[str, Any]], list[dict[str, Any]]]]:
    """Compares all files with the same name in two folders.
    Args:
        dir1, dir2 (str): _description_
        dir2 (_type_): _description_
        file_filter (str, optional): Defaults to "*.txt".

    Returns:
        dict[tuple[str], tuple[dict[str, Any]], list[dict[str, Any]]]: _description_
    """
    dir1_files = glob(os.path.join(dir1, file_filter))
    dir2_files = glob(os.path.join(dir2, file_filter))

    common_files = set(os.path.basename(f) for f in dir1_files).intersection(
        set(os.path.basename(f) for f in dir2_files)
    )

    differences = {}
    for file in common_files:
        file1 = os.path.join(dir1, file)
        file2 = os.path.join(dir2, file)

        msg = "Analyzing " + os.path.basename(file1) + "."
        if not filecmp.cmp(file1, file2, shallow=False):
            msg += " Files are different, performing detailed analysis."
            differences[file] = compare_file_contents(file1, file2)
        else:
            differences[file] = NO_DIFFERENCES
        LOGGER.info(msg)

    return sorted_dict(differences)


def print_lines(stream: TextIOWrapper, lines: dict[str, Any], tab1: str, tab2: str) -> str:
    def line_key(line):
        return f"({line.get(ABSTIME, line.get(ABSTIME.upper()))},{line[BEAT_ID]},{line[PASS_ID]},{line.get(POSITION_ID,line.get(POSITION_ID.upper()) )})"

    if isinstance(lines, list):
        for nr, line in enumerate(lines):
            stream.write(f"{tab1 if nr==0 else tab2}{line} -- {line_key(line)}\n")
    else:
        stream.write(tab1 + f"{lines} -- {line_key(lines)}\n")


TAB0 = " " * 5
TAB1 = " " * 10
TAB2 = TAB1 + "  - "
TAB3A = TAB1 + "  > "
TAB3B = TAB1 + "    "


def save_file_summary(stream: TextIOWrapper, summary: dict[str, dict[str, str]], detailed: bool) -> None:
    for key, items in summary.items():
        stream.write(TAB0 + f"{key}{": " if items else ""}{len(items) if items else ""}\n")
        if detailed:
            for lines1, lines2 in items:
                print_lines(stream, lines1, TAB2, TAB2)
                print_lines(stream, lines2, TAB3A, TAB3B)


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
    LOGGER.info("Analyzing " + os.path.basename(filepath_old))
    if not filecmp.cmp(filepath_old, filepath_new, shallow=False):
        LOGGER.info(os.path.basename(filepath_old) + " has differences, analyzing files in detail.")
        differences = compare_file_contents(filepath_old, filepath_new)
    else:
        differences = NO_DIFFERENCES

    # save report to file
    filepath_out = os.path.split(filepath_new)[0]
    LOGGER.info("saving results")
    with open(os.path.join(filepath_out, "comparison.txt"), "w", encoding="utf-8") as outfile:
        outfile.write(os.path.split(filepath_old)[1] + "\n")
        save_file_summary(outfile, summary=differences, detailed=False)
    with open(os.path.join(filepath_out, "comparison_details.txt"), "w", encoding="utf-8") as outfile:
        outfile.write(os.path.split(filepath_old)[1] + "\n")
        save_file_summary(outfile, summary=differences, detailed=True)


def compare_all(ref_dir: str, other_dir: str) -> bool:
    """Compares all matching midi files in two directories
       or compares two files.
    Args:
        dir_old (_type_): First folder
        dir_new (_type_): Second folder
    """
    # 1. convert midi files to text files
    files = []
    for folder in [ref_dir, other_dir]:
        files.append(set([os.path.basename(path) for path in glob(os.path.join(folder, "*.mid"))]))
    filelist = files[0].intersection(files[1])
    LOGGER.info("Generating .TXT files from MIDI files")
    to_text_multiple_files(filelist, [ref_dir, other_dir])

    # 2. compare the text files
    LOGGER.info("Comparing .TXT files in `reference` and `output` folder")
    differences = compare_directories(ref_dir, other_dir, "*.txt")
    no_differences_found = all(diff == NO_DIFFERENCES for diff in differences.values())

    # 3. save report to file
    LOGGER.info("Saving summary report in comparison.txt")
    with open(os.path.join(other_dir, "comparison.txt"), "w", encoding="utf-8") as outfile:
        for file, diff in differences.items():
            outfile.write(f"Differences in {file}:\n")
            save_file_summary(outfile, summary=diff, detailed=False)
    LOGGER.info("Saving detailed report in comparison_details.txt")
    with open(os.path.join(other_dir, "comparison_details.txt"), "w", encoding="utf-8") as outfile:
        for file, diff in differences.items():
            outfile.write(f"Differences in {file}:\n")
            save_file_summary(outfile, summary=diff, detailed=True)

    return no_differences_found


if __name__ == "__main__":
    REF_DIR = "./tests/data/notation/_integration_test/reference"
    OTHER_DIR = "./tests/data/notation/_integration_test/output"
    RUNALL = True
    if RUNALL:
        compare_all(REF_DIR, OTHER_DIR)
    else:
        FILENAME = "Sinom Ladrang (GK)_full_GAMELAN1.txt"
        compare_txt_files(os.path.join(REF_DIR, FILENAME), os.path.join(OTHER_DIR, FILENAME))
