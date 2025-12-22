import argparse
import os
from datetime import datetime

import pandas as pd

from ohcoach_cell_tools.common.logger import Logger
from scripts.datetime_converter.messages import (
    get_bs_message_bytes,
    get_end_message,
    get_gps_message_bytes,
    get_imu_message_bytes,
    get_start_message,
)

logger = Logger("Converter")
CONVERTER_DIR = "scripts/datetime_converter"
RESULTS_DIR = f"{CONVERTER_DIR}/results"
os.makedirs(RESULTS_DIR, exist_ok=True)


def __get_df(file_path: str) -> pd.DataFrame:
    return pd.read_csv(file_path, dtype=str)


def __get_gps_messages(file_path: str, datetime_obj: datetime) -> list:
    rgp_data = __get_df(file_path=file_path)
    rgp_data["datetime"] = pd.date_range(start=datetime_obj, periods=len(rgp_data), freq="0.1S")
    rgp_data.to_csv(f"{RESULTS_DIR}/CLBX-4B-41561_5.9_0_1662001969_0_1.rgp", index=False)

    gps_messages = []
    for rgp in rgp_data.itertuples():
        gps_messages.append(get_gps_message_bytes(rgp))

    return gps_messages


def __get_imu_messages(file_path: str, datetime_obj: datetime) -> list:
    rim_data = __get_df(file_path=file_path)
    rim_data["datetime"] = pd.date_range(start=datetime_obj, periods=len(rim_data), freq="0.01S")
    rim_data.to_csv(f"{RESULTS_DIR}/CLBX-4B-41561_5.9_0_1662001969_0_1.rim", index=False)

    imu_messages = []
    for rim in rim_data.itertuples():
        imu_messages.append(get_imu_message_bytes(rim))

    return imu_messages


def __get_bs_messages(file_path: str, datetime_obj: datetime) -> list:
    rbs_data = __get_df(file_path=file_path)
    rbs_data["datetime"] = pd.date_range(start=datetime_obj, periods=len(rbs_data), freq="1S")
    rbs_data.to_csv(f"{RESULTS_DIR}/CLBX-4B-41561_5.9_0_1662001969_0_1.rbs", index=False)

    bs_messages = []
    for rbs in rbs_data.itertuples():
        bs_messages.append(get_bs_message_bytes(rbs))

    return bs_messages


def __make_ftg_file(ftg_messages: list):
    with open(f"{RESULTS_DIR}/CLBX-4B-41561_5.9_0_1662001969.ftg", "wb") as f:
        for message in ftg_messages:
            f.write(message)


def run(_date: str, _time: str):
    datetime_str = f"{_date} {_time}"
    try:
        datetime_obj = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"Invalid datetime - {e}")
        raise e

    ftg_messages = []
    ftg_messages.append(get_start_message())
    logger.info("Success to get start message")

    ftg_messages += __get_gps_messages(
        file_path=f"{CONVERTER_DIR}/CLBX-4B-41561_5.9_0_1662001969_0.rgp_0.csv",
        datetime_obj=datetime_obj,
    )
    logger.info("Success to get gps message")

    ftg_messages += __get_imu_messages(
        file_path=f"{CONVERTER_DIR}/CLBX-4B-41561_5.9_0_1662001969_0.rim_0.csv",
        datetime_obj=datetime_obj,
    )
    logger.info("Success to get imu message")

    ftg_messages += __get_bs_messages(
        file_path=f"{CONVERTER_DIR}/CLBX-4B-41561_5.9_0_1662001969_0.rbs_0.csv",
        datetime_obj=datetime_obj,
    )
    logger.info("Success to get bs message")

    ftg_messages.append(get_end_message())
    logger.info("Success to get end message")

    __make_ftg_file(ftg_messages)
    logger.info("Success to get ftg file")


def start():
    parser = argparse.ArgumentParser(description="A Script for datetime converter")

    parser.add_argument(
        "date",
        type=str,
        help="date you want to change (ex. 2022-02-22)",
    )
    parser.add_argument(
        "--time",
        "-t",
        type=str,
        default="00:00:00",
        help="time you want to change (defalut 00:00:00)",
    )

    args = parser.parse_args()

    run(_date=args.date, _time=args.time)


if __name__ == "__main__":
    start()
