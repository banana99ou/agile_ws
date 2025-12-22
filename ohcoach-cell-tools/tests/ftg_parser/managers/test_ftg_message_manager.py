from datetime import datetime

import pandas as pd

from ohcoach_cell_tools.constants import LABEL_DATETIME
from ohcoach_cell_tools.ftg_parser.managers.bs_message_manager import BsMessageManager
from ohcoach_cell_tools.ftg_parser.managers.ftg_message_manager import MessageManager
from ohcoach_cell_tools.ftg_parser.managers.gps_message_manager import GpsMessageManager
from ohcoach_cell_tools.ftg_parser.managers.imu_message_manager import ImuMessageManager

initial_columns = ("a", "b")
metadata_added_columns = ("a", "b", "file_name", "intermed_index")

initial_exported_rows = [
    (1, 2),
    (2, 3),
]

metadata_added_exported_rows = [
    (1, 2, "file_name", 1),
    (2, 3, "file_name", 1),
]

expected_list_of_dict = [
    {"a": 1, "b": 2},
    {"a": 2, "b": 3},
]

expected_bulk_insert_form = [
    {
        "a": 1,
        "b": 2,
        "start_data_id": 1,
    },
    {
        "a": 2,
        "b": 3,
        "start_data_id": 1,
    },
]

expected_combined_db_insert_form = [
    {
        "a": 1,
        "b": 2,
        "file_name": "file_name",
        "intermed_index": 1,
        "start_data_id": 1,
    },
    {
        "a": 2,
        "b": 3,
        "file_name": "file_name",
        "intermed_index": 1,
        "start_data_id": 1,
    },
]

datetime_rows_with_reversed_time = [
    (datetime(1900, 1, 1, 17, 42, 32, 820000),),
    (datetime(1900, 1, 1, 17, 42, 32, 830000),),
    (datetime(1900, 1, 1, 17, 42, 32, 840000),),
    (datetime(1900, 1, 1, 17, 42, 32, 850000),),
    (datetime(1900, 1, 1, 17, 42, 32, 860000),),
    (datetime(1900, 1, 1, 17, 41, 32, 820000),),
    (datetime(1900, 1, 1, 17, 41, 32, 830000),),
    (datetime(1900, 1, 1, 17, 41, 32, 840000),),
    (datetime(1900, 1, 1, 17, 42, 32, 870000),),
    (datetime(1900, 1, 1, 17, 42, 32, 880000),),
    (datetime(1900, 1, 1, 23, 59, 59, 980000),),
    (datetime(1900, 1, 1, 23, 59, 59, 990000),),
    (datetime(1900, 1, 1, 00, 00, 00),),
    (datetime(1900, 1, 1, 00, 00, 00, 10000),),
]

expected_datetime_rows_with_no_reversed_time = [
    (datetime(1900, 1, 1, 17, 42, 32, 820000),),
    (datetime(1900, 1, 1, 17, 42, 32, 830000),),
    (datetime(1900, 1, 1, 17, 42, 32, 840000),),
    (datetime(1900, 1, 1, 17, 42, 32, 850000),),
    (datetime(1900, 1, 1, 17, 42, 32, 860000),),
    (datetime(1900, 1, 1, 17, 42, 32, 870000),),
    (datetime(1900, 1, 1, 17, 42, 32, 880000),),
    (datetime(1900, 1, 1, 23, 59, 59, 980000),),
    (datetime(1900, 1, 1, 23, 59, 59, 990000),),
    (datetime(1900, 1, 1, 00, 00, 00),),
    (datetime(1900, 1, 1, 00, 00, 00, 10000),),
]

datetime_rows_with_reversed_time_end_cursor = [
    (datetime(2020, 4, 24, 17, 42, 32, 820000),),
    (datetime(2020, 4, 24, 17, 42, 25, 820000),),
    (datetime(2020, 4, 24, 17, 42, 26, 820000),),
    (datetime(2020, 4, 24, 17, 42, 27, 820000),),
    (datetime(2020, 4, 24, 17, 42, 28, 820000),),
    (datetime(2020, 4, 24, 17, 42, 29, 820000),),
    (datetime(2020, 4, 24, 17, 42, 30, 820000),),
    (datetime(2020, 4, 24, 17, 42, 31, 820000),),
    (datetime(2020, 4, 24, 17, 42, 32, 820000),),
]

expected_datetime_rows_with_reversed_time_end_cursor = [
    (datetime(2020, 4, 24, 17, 42, 32, 820000),),
]


class TestMessageManager:
    def test_message_length_for_each_concrete_manager(self):
        # Given: gps/imu/bs message manager
        gps_manager = GpsMessageManager()
        imu_manager = ImuMessageManager()
        bs_manager = BsMessageManager()

        # Then: each manager calls message_length which result should match the expected length
        GPS_MSG_LENGTH = 52
        IMU_MSG_LENGTH = 22
        BS_MSG_LENGTH = 24

        assert gps_manager.message_length == GPS_MSG_LENGTH
        assert imu_manager.message_length == IMU_MSG_LENGTH
        assert bs_manager.message_length == BS_MSG_LENGTH

    def test_drop_reversed_datetime_rows(self):
        # Given: initial dataframe which has datetime problem
        dataframe = pd.DataFrame(datetime_rows_with_reversed_time, columns=[LABEL_DATETIME])

        # When: call drop_reversed_datetime_rows
        MessageManager.drop_reversed_datetime_rows(dataframe)

        expected_dataframe = pd.DataFrame(
            expected_datetime_rows_with_no_reversed_time,
            columns=[LABEL_DATETIME],
        )

        # Then: datetime order is corrected and date changing rows are not dropped
        dataframe.set_index([LABEL_DATETIME], inplace=True)
        expected_dataframe.set_index([LABEL_DATETIME], inplace=True)

        assert dataframe.equals(expected_dataframe)

    def test_drop_reversed_datetime_rows_row_cursor_equal_end_cursor(self):
        # Given: initial dataframe which has datetime problem
        dataframe = pd.DataFrame(
            datetime_rows_with_reversed_time_end_cursor, columns=[LABEL_DATETIME]
        )

        # When: call drop_reversed_datetime_rows and datetime reversal occurs until the last row
        MessageManager.drop_reversed_datetime_rows(dataframe)

        expected_dataframe = pd.DataFrame(
            expected_datetime_rows_with_reversed_time_end_cursor,
            columns=[LABEL_DATETIME],
        )

        # Then: dataframe last row not exceeded
        dataframe.set_index([LABEL_DATETIME], inplace=True)
        expected_dataframe.set_index([LABEL_DATETIME], inplace=True)

        assert dataframe.equals(expected_dataframe)
