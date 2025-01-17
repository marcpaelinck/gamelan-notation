import difflib
import filecmp
import os
from glob import glob


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

    return differences


def main():
    path_old = "./data/notation/_parserold"
    path_new = "./data/notation/_parsernew"
    differences = compare_directories(path_old, path_new)

    with open(os.path.join(path_old, "comparison.txt"), "w") as outfile:
        if differences:
            for file, diff in differences.items():
                outfile.write(f"Differences in {file}:")
                for line in diff:
                    outfile.write(line)
        else:
            outfile.write("No differences found.")


if __name__ == "__main__":
    main()
