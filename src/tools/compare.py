"""
Compares MIDI files contained in two folders and outputs the differences in a file. Only files with the same name are compared.
The comparison is performed by first creating a text (.txt) version of all .mid files which contains a readable version
of the MIDI messages, and then comparing these text files.
The output is stored in the first of the two folders.
"""

import difflib
import filecmp
import os
from glob import glob

from src.tools.print_midi_file import to_text_multiple_files


def list_files(directory):
    return [os.path.join(directory, f) for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]


def compare_files(file1, file2):
    with open(file1, "r") as f1, open(file2, "r") as f2:
        f1_lines = f1.readlines()
        f2_lines = f2.readlines()

    diff = difflib.unified_diff(f1_lines, f2_lines, fromfile=file1, tofile=file2)
    return list(diff)


def compare_directories(dir1, dir2, filter="*.txt"):
    dir1_files = glob(os.path.join(dir1, filter))
    dir2_files = glob(os.path.join(dir2, filter))

    common_files = set(os.path.basename(f) for f in dir1_files).intersection(
        set(os.path.basename(f) for f in dir2_files)
    )

    differences = {}
    for file in common_files:
        file1 = os.path.join(dir1, file)
        file2 = os.path.join(dir2, file)

        if not filecmp.cmp(file1, file2, shallow=False):
            differences[file] = compare_files(file1, file2)
        else:
            differences[file] = " No differences"

    return differences


def compare_all(dir_old, dir_new):
    # 1. convert midi files to text files
    files = []
    for dir in [dir_old, dir_new]:
        files.append(set([os.path.basename(path) for path in glob(os.path.join(dir, "*.mid"))]))
    filelist = files[0].intersection(files[1])
    # to_text_multiple_files(filelist, [dir_old, dir_new])
    to_text_multiple_files(filelist, [dir_new])

    # 2. compare the text files
    differences = compare_directories(dir_old, dir_new, "*.txt")

    with open(os.path.join(dir_old, "comparison.txt"), "w") as outfile:
        if differences:
            for file, diff in differences.items():
                outfile.write(f"Differences in {file}:")
                for line in diff:
                    outfile.write(line)
                outfile.write("\n")
        else:
            outfile.write("No differences found.")


if __name__ == "__main__":
    dir_old = "./data/notation/_parserold"
    dir_new = "./data/notation/_parsernew"
    compare_all(dir_old, dir_new)
