import argparse
import os
import re
from collections import defaultdict
from typing import Optional

import pandas as pd

from scripts.veritication_func.action_aggregate import ActionAggregate
from scripts.veritication_func.common import (
    ACTION,
    COMPUTED,
    get_file_list,
    make_path_and_create_folders,
)
from scripts.veritication_func.computed_aggregate import ComputedAggregate
from scripts.veritication_func.interval_summary import IntervalSummary
from scripts.veritication_func.session_aggregate import SessionAggregate


def create_verification(
    source: str,
    result_paths: tuple[str, str, str, str],
    action_data_detail_datetime: Optional[str],
    session_data_formation_datetime: Optional[list[str]],
    session_data_heatmap_stadium: Optional[list[int]],
):
    computed_path, action_path, interval_summary_path, session_path = result_paths
    file_full_list = get_file_list(source)
    interval_summary_dict = defaultdict(lambda: {COMPUTED: False, ACTION: False})
    action_aggregate = ActionAggregate()
    computed_aggregate = ComputedAggregate()
    session_aggregate = SessionAggregate()

    for name in file_full_list:
        if not name.endswith(".csv"):
            print("skip")
            continue

        df = pd.read_csv(name)
        basename = os.path.basename(name)
        file_name = basename.replace(".csv", ".json")
        interval_summary_key = re.split(rf"{COMPUTED}|{ACTION}", file_name)[0]
        interval_summary_dict[interval_summary_key]

        if ACTION in basename:
            action_aggregate.df = df
            action_aggregate.create_action_aggreagte_json(action_path, file_name)
            if action_data_detail_datetime:
                action_aggregate.create_action_data_detail_aggreagte_json(
                    action_data_detail_datetime, action_path, file_name
                )
            if session_data_formation_datetime:
                session_aggregate.df = df
                session_aggregate.create_session_data_formation_aggreagte_json(
                    session_data_formation_datetime, session_path, file_name
                )
            if session_data_heatmap_stadium:
                session_aggregate.df = df
                session_aggregate.create_session_data_heatmap_aggreagte_json(
                    session_data_heatmap_stadium, session_path, file_name
                )
            interval_summary_dict[interval_summary_key][ACTION] = True

        elif COMPUTED in basename:
            computed_aggregate.df = df
            computed_aggregate.create_computed_aggreagte_json(computed_path, file_name)
            if session_data_heatmap_stadium:
                session_aggregate.df = df
                session_aggregate.create_session_data_heatmap_aggreagte_json(
                    session_data_heatmap_stadium, session_path, file_name
                )
            interval_summary_dict[interval_summary_key][COMPUTED] = True
        else:
            print(f"The {basename} file name does not contain computed or action")
            continue

        if (
            interval_summary_dict[interval_summary_key][COMPUTED]
            and interval_summary_dict[interval_summary_key][ACTION]
        ):
            interval_summary = IntervalSummary(df, name, basename)
            interval_summary.create_interval_summary_json(
                interval_summary_path, interval_summary_key
            )


def run(
    source: str,
    destination: Optional[str] = None,
    action_data_detail_datetime: Optional[str] = None,
    session_data_formation_datetime: Optional[list[str]] = None,
    session_data_heatmap_stadium: Optional[list[int]] = None,
):
    if destination is None:
        destination = os.path.dirname(source) if os.path.isfile(source) else source
    result_paths = make_path_and_create_folders(destination)
    create_verification(
        source,
        result_paths,
        action_data_detail_datetime,
        session_data_formation_datetime,
        session_data_heatmap_stadium,
    )


def start():
    verification = argparse.ArgumentParser(
        description="A Script for Computed, Action csv data Verification"
    )

    verification.add_argument(
        "source", type=str, help="place where computed, action files are stroed"
    )

    verification.add_argument(
        "--destination", "-d", type=str, help="place where result files will be stroed"
    )

    verification.add_argument(
        "--action_data_detail_datetime",
        "-ad",
        type=str,
        help="Write the action data detail datetime to aggregate",
    )

    verification.add_argument(
        "--session_data_formation_datetime",
        "-formation",
        nargs="+",
        type=str,
        help="Write the sesstion data formaion datetime to aggregate",
    )

    verification.add_argument(
        "--session_data_heatmap_stadium",
        "-heatmap",
        nargs="+",
        type=int,
        help="Write the sesstion data heatmap stadium coordinate to aggregate",
    )

    args = verification.parse_args()
    print(args.source)

    run(
        args.source,
        args.destination,
        args.action_data_detail_datetime,
        args.session_data_formation_datetime,
        args.session_data_heatmap_stadium,
    )


if __name__ == "__main__":
    start()
