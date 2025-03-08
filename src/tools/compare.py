"""
Compares MIDI files contained in two folders and outputs the differences in a file. Only files with the same name are
compared. The comparison is performed by first creating a text (.txt) version of all .mid files which contains a
readable version of the MIDI messages, and then comparing these text files.
The output is stored in the first of the two folders.
"""

import difflib
import filecmp
import os
from glob import glob

from src.common.logger import get_logger
from src.tools.print_midi_file import to_text, to_text_multiple_files

LOGGER = get_logger(__name__)


def compare_two_files(file1: str, file2: str) -> str:
    """Compares two files and returns the differences in a unified diff format.
    Args:
        file1, file2 (_type_): path to the files
    Returns:
        str: The differences.
    """
    with open(file1, "r", encoding="utf-8") as f1, open(file2, "r", encoding="utf-8") as f2:
        # Remove additional marker messages that are added to the test output for easier location of differences
        f1_lines = [line for line in f1.readlines() if not "MetaMessage('marker', text='b_" in line]
        f2_lines = [line for line in f2.readlines() if not "MetaMessage('marker', text='b_" in line]

    diff = difflib.unified_diff(f1_lines, f2_lines, fromfile=file1, tofile=file2)
    # TODO consuming the first line if there are differences
    if not next(diff, None):
        diff = ["No differences\n"]
    return list(diff)


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
        file1 = os.path.join(dir1, file)
        file2 = os.path.join(dir2, file)

        if not filecmp.cmp(file1, file2, shallow=False):
            differences[file] = compare_two_files(file1, file2)
        else:
            differences[file] = " No differences"

    return differences


def compare_files(folderpath: str, file_old: str, file_new: str, outfile: str = "comparison.txt"):
    """Compares two files
    Args:
        folderpath: (str): path containing the files
        dir_old (str): First folder
        dir_new (str): Second folder
        folders (bool, optional): If False, paths to two separate files will be expected. Defaults to True.
    """
    # 1. convert midi files to text files
    to_text(folderpath, file_old)
    to_text(folderpath, file_new)

    # 2. compare the text files
    txt_old = os.path.splitext(file_old)[0] + ".txt"
    txt_new = os.path.splitext(file_new)[0] + ".txt"
    path1 = os.path.join(folderpath, txt_old)
    path2 = os.path.join(folderpath, txt_new)
    if not filecmp.cmp(path1, path2, shallow=False):
        differences = compare_two_files(path1, path2)
    else:
        differences = ["No differences\n"]

    # 3. save report to file
    with open(os.path.join(folderpath, outfile), "w", encoding="utf-8") as outfile:
        for line in differences:
            outfile.write(line)


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
        if differences:
            for file, diff in differences.items():
                outfile.write(f"Differences in {file}:\n")
                for line in diff:
                    outfile.write(line)
                outfile.write("\n")
        else:
            outfile.write("No differences found.")


if __name__ == "__main__":
    REF_DIR = "./data/notation/_integration_test/reference"
    OTHER_DIR = "./data/notation/_integration_test/output"
    compare_all(REF_DIR, OTHER_DIR)
    # file_old = "Cendrawasih_entire piece_GAMELAN1.mid"
    # file_new = "Test Gong Kebyar_Cendrawasih_GAMELAN1.mid"
    # compare_files("./data/notation/test", file_old, file_new)
