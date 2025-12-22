import sys, os, re
# Add parent directory (ohcoach-cell-tools) to path so ohcoach_cell_tools can be imported
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
import argparse
from typing import List, Optional, Tuple, NamedTuple

import pandas as pd
from multiprocessing import Pool

from ohcoach_cell_tools.constants import LABEL_DATETIME
from ohcoach_cell_tools.ftg_parser.ftg_parser import FtgParser

PATH_RGP = "results/rgp"
PATH_RIM = "results/rim"
PATH_RBS = "results/rbs"
FITO_LOG_START_DELIMITER_PATTERN = re.compile(br"\(\d{8}\)")

def make_path_and_create_folders(path: str) -> Tuple[str, str, str]:
    paths = (
        os.path.join(path, PATH_RGP),
        os.path.join(path, PATH_RIM),
        os.path.join(path, PATH_RBS),
    )

    for dir_path in paths:
        os.makedirs(dir_path, exist_ok=True)

    return paths


def get_file_list(source: str) -> List[str]:
    if os.path.isfile(source):
        return [source]

    return [path for file in os.listdir(source) if (path := os.path.join(source, file))]


def time_gap_error_info_true_false_converter(value_counts: pd.Series) -> pd.Series:
    value_count = {True: 0, False: 0}
    for name, value in value_counts.items():
        value_count[name] = value
    return pd.Series(value_count)


def add_time_gap_error_info(rgp: pd.DataFrame, rim: pd.DataFrame, rbs: pd.DataFrame) -> None:
    rgp["gap"] = rgp[LABEL_DATETIME].diff() == pd.Timedelta(value=0.1, unit="sec")
    rim["gap"] = rim[LABEL_DATETIME].diff() == pd.Timedelta(value=0.01, unit="sec")
    rbs["gap"] = rbs[LABEL_DATETIME].diff() == pd.Timedelta(value=1, unit="sec")

    rgp_gap_counts = time_gap_error_info_true_false_converter(rgp["gap"].value_counts())
    rim_gap_counts = time_gap_error_info_true_false_converter(rim["gap"].value_counts())
    rbs_gap_counts = time_gap_error_info_true_false_converter(rbs["gap"].value_counts())

    print(
        "RGP TIME GAP:",
        f"{rgp_gap_counts.at[0]}/{rgp_gap_counts[0] + rgp_gap_counts[1]}",
        "RIM TIME GAP:",
        f"{rim_gap_counts.at[0]}/{rim_gap_counts[0] + rim_gap_counts[1]}",
        "RBS TIME GAP:",
        f"{rbs_gap_counts.at[0]}/{rbs_gap_counts[0] + rbs_gap_counts[1]}",
    )


def create_rgp_rim_rbs_csv_to_folder(
    result_dir: str,
    basename: str,
    i: int,
    rgp: pd.DataFrame,
    rim: pd.DataFrame,
    rbs: pd.DataFrame,
) -> None:
    rgp_path = os.path.join(result_dir, basename.replace(".ftg", f"_{i}_1rgp_{i}.csv"))
    rim_path = os.path.join(result_dir, basename.replace(".ftg", f"_{i}_2rim_{i}.csv"))
    rbs_path = os.path.join(result_dir, basename.replace(".ftg", f"_{i}_3rbs_{i}.csv"))

    rgp.to_csv(rgp_path)
    rim.to_csv(rim_path)
    rbs.to_csv(rbs_path)


def start_end_to_txt(result_dir: str, basename: str, i: int, obj: NamedTuple, start: bool) -> None:
    save_path = os.path.join(result_dir, basename.replace(".ftg", f"_{i}_{'4start' if start else '5end'}_{i}.txt"))
    with open(save_path, "w") as f:
        try:
            for key, value in obj._asdict().items():
                f.write(f"{key}={value}\n")
        except AttributeError as e:
            print(f"'{basename}' cycle number {i+1} {'start' if start else 'end'} message not found.")

def error_to_txt(result_dir: str, basename: str, i: int, errors: List[str]) -> None:
    save_path = os.path.join(result_dir, basename.replace(".ftg", f"_{i}_0error_{i}.txt"))
    with open(save_path, "w") as f:
        for error in errors:
            f.write(f"{error}\n")

def parse_one_file(path: str, result_dir: str):
    if not path.endswith(".ftg"):
        print(f"path: {path} is not ftg file.. skip!")
        return
    basename = os.path.basename(path)

    with open(path, "rb") as f:
        contents = f.read()
    
    max_cursor = sys.maxsize
    match = FITO_LOG_START_DELIMITER_PATTERN.search(contents)
    if match:
        max_cursor = match.start()
        log_data = contents[max_cursor:].decode("utf-8", errors="replace").strip()
        save_path = os.path.join(result_dir, basename.replace(".ftg", f"_log.txt"))
        with open(save_path, "w") as f:
            f.write(log_data)

    try:
        for i, (start, rgp, rim, rbs, end, errors) in enumerate(FtgParser.parse(contents)):
            # print(f"index: {i} / {errors}")
            # add_time_gap_error_info(rgp, rim, rbs)
            start_end_to_txt(result_dir, basename, i, start, start=True)
            create_rgp_rim_rbs_csv_to_folder(
                result_dir, basename, i, rgp, rim, rbs
            )
            start_end_to_txt(result_dir, basename, i, end, start=False)
            error_to_txt(result_dir, basename, i, errors)
            
            print(f"'{basename}' cycle number {i+1} is saved.")
        ftg_dir = result_dir.replace("results", "ftg")
        os.rename(path, os.path.join(ftg_dir, basename))
    except Exception as e:
        print(f"########## {path} * EXCEPTION: {e} ###########")
        raise e
    finally:
        FtgParser.parsing_errors.clear()

def parse(source: str, destination: Optional[str] = None):
    if not destination:
        destination = os.path.dirname(source) if os.path.isfile(source) else source

    result_dir = os.path.join(destination, "results")
    os.makedirs(result_dir, exist_ok=True)
    os.makedirs(result_dir.replace("results", "ftg"), exist_ok=True)

    file_full_list = get_file_list(source)
    import time
    start_time = time.perf_counter()
    with Pool() as pool:
        pool.starmap(parse_one_file, [(path, result_dir) for path in file_full_list])
    # for path in file_full_list:
    #     parse_one_file(path, result_dir)
    elapsed_time = time.perf_counter() - start_time
    print(f"Elapsed Time: {elapsed_time:.3f} sec")


def start():
    parser = argparse.ArgumentParser(description="A Script for Ohcoach Cell Data Parsing")

    parser.add_argument(
        "source",
        type=str,
        help="place where ftg files are stored",
    )
    parser.add_argument(
        "--destination",
        "-d",
        type=str,
        help="place where result files will be stored",
    )

    args = parser.parse_args()

    parse(args.source, destination=args.destination)


if __name__ == "__main__":
    start()
