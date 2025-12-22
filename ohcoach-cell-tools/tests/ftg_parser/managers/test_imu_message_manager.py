from datetime import datetime

import pandas as pd
import pytest

from ohcoach_cell_tools.constants import IMU_EXPORT_COLUMNS
from ohcoach_cell_tools.ftg_parser.managers.ftg_message_manager import MessageManager
from ohcoach_cell_tools.ftg_parser.managers.imu_message_manager import ImuMessageManager

raw_imu_messages = [
    b"\xb2\xdb\t\x01\xff6\x00'\xf7(\xff\x95\x00\x04\xff\xf7M\x01\xf1\x00\x9d\xfe",
    b"\xb3\xdb\t\x01\xff3\x00*\xf7!\xff\x96\x00\x05\xff\xf8M\x01\xf1\x00\x9d\xfe",
    b"\xb4\xdb\t\x01\xff3\x00*\xf7 \xff\x96\x00\x04\xff\xf8M\x01\xf1\x00\x9d\xfe",
    b"\xb5\xdb\t\x01\xff3\x00(\xf7\x19\xff\x96\x00\x03\xff\xf9M\x01\xf1\x00\x9d\xfe",
    b"\xb6\xdb\t\x01\xff6\x00*\xf7\x18\xff\x96\x00\x04\xff\xf8M\x01\xf1\x00\x9d\xfe",
]

expected_exported_rows = [
    b"\xb2\xdb\t\x016\xff'\x00(\xf7\x95\xff\x04\x00\xf7\xffM\x01\xf1\x00\x9d\xfe",
    b"\xb3\xdb\t\x013\xff*\x00!\xf7\x96\xff\x05\x00\xf8\xffM\x01\xf1\x00\x9d\xfe",
    b"\xb4\xdb\t\x013\xff*\x00 \xf7\x96\xff\x04\x00\xf8\xffM\x01\xf1\x00\x9d\xfe",
    b"\xb5\xdb\t\x013\xff(\x00\x19\xf7\x96\xff\x03\x00\xf9\xffM\x01\xf1\x00\x9d\xfe",
    b"\xb6\xdb\t\x016\xff*\x00\x18\xf7\x96\xff\x04\x00\xf8\xffM\x01\xf1\x00\x9d\xfe",
]


expected_exported_dataframe = pd.DataFrame(
    [
        [pd.Timestamp("1900-01-01 17:42:32.820000"), -202, 39, -2264, -107, 4, -9, 333, 241, -355],
        [pd.Timestamp("1900-01-01 17:42:32.830000"), -205, 42, -2271, -106, 5, -8, 333, 241, -355],
        [pd.Timestamp("1900-01-01 17:42:32.840000"), -205, 42, -2272, -106, 4, -8, 333, 241, -355],
        [pd.Timestamp("1900-01-01 17:42:32.850000"), -205, 40, -2279, -106, 3, -7, 333, 241, -355],
        [pd.Timestamp("1900-01-01 17:42:32.860000"), -202, 42, -2280, -106, 4, -8, 333, 241, -355],
    ],
    columns=IMU_EXPORT_COLUMNS,
).astype(
    dtype={
        "acc_x": "int16",
        "acc_y": "int16",
        "acc_z": "int16",
        "gyro_x": "int16",
        "gyro_y": "int16",
        "gyro_z": "int16",
        "magnet_x": "int16",
        "magnet_y": "int16",
        "magnet_z": "int16",
    }
)


date_to_adjust = datetime(2020, 4, 11, 17, 42, 32, 810000)

expected_date_adjusted_rows = [
    (datetime(2020, 4, 11, 17, 42, 32, 820000), -202, 39, -2264, -107, 4, -9, 333, 241, -355),
    (datetime(2020, 4, 11, 17, 42, 32, 830000), -205, 42, -2271, -106, 5, -8, 333, 241, -355),
    (datetime(2020, 4, 11, 17, 42, 32, 840000), -205, 42, -2272, -106, 4, -8, 333, 241, -355),
    (datetime(2020, 4, 11, 17, 42, 32, 850000), -205, 40, -2279, -106, 3, -7, 333, 241, -355),
    (datetime(2020, 4, 11, 17, 42, 32, 860000), -202, 42, -2280, -106, 4, -8, 333, 241, -355),
]


@pytest.fixture
def imu_message_manager():
    message_manager = ImuMessageManager()

    for raw_message in raw_imu_messages:
        message_manager.add_message(raw_message)

    yield message_manager


class TestImuMessageManager:
    def test_add_message(self):
        # Given: ImuMessageManager instance and raw imu messages
        imu_message_manager = ImuMessageManager()

        # When: ImuMessageManager.add_message is called on raw imu messages
        for raw_message in raw_imu_messages:
            imu_message_manager.add_message(raw_message)

        # Then: list of added (tuple-converted) messages should eqaul as expected list of tuples
        assert imu_message_manager.messages == expected_exported_rows

    def test_export_dataframe(self, imu_message_manager):
        # When: ImuMessageManager.export_dataframe is called
        actual_dataframe = imu_message_manager.export_dataframe()

        # Then: exported dataframe should returned as expected
        pd.testing.assert_frame_equal(actual_dataframe, expected_exported_dataframe)

        # And: messages list should empty
        assert not imu_message_manager.messages

    def test_clear(self, imu_message_manager):
        # When: call clear method
        imu_message_manager.clear()

        # Then: messages list should be empty
        assert imu_message_manager.messages == []

    def test_adjust_date_when_date_changes_in_series_of_datetime(self):
        exptected_rows = [
            (
                datetime(2020, 4, 11, 23, 59, 59, 990000),
                -202,
                39,
                -2264,
                -107,
                4,
                -9,
                333,
                241,
                -355,
            ),
            (
                datetime(2020, 4, 12, 00, 00, 00, 000000),
                -205,
                42,
                -2271,
                -106,
                5,
                -8,
                333,
                241,
                -355,
            ),
        ]

        expected_dataframe = pd.DataFrame(exptected_rows, columns=IMU_EXPORT_COLUMNS)

        # Given: sample exported rows in which the date changes & reference date
        date_changing_input_rows = [
            (
                datetime(1900, 1, 1, 23, 59, 59, 990000),
                -202,
                39,
                -2264,
                -107,
                4,
                -9,
                333,
                241,
                -355,
            ),
            (
                datetime(1900, 1, 1, 00, 00, 00, 000000),
                -205,
                42,
                -2271,
                -106,
                5,
                -8,
                333,
                241,
                -355,
            ),
        ]

        reference_date = datetime(2020, 4, 11, 17, 42, 32, 810000)

        # When: ImuMessageManager.adjust_date is called
        actual_dataframe = MessageManager.adjust_date(
            pd.DataFrame(date_changing_input_rows, columns=IMU_EXPORT_COLUMNS),
            reference_date,
        )

        # Then: date is adjusted correctly
        assert actual_dataframe.equals(expected_dataframe)

    def test_adjust_date(self):
        expected_dataframe = pd.DataFrame(expected_date_adjusted_rows, columns=IMU_EXPORT_COLUMNS)

        # When: ImuMessageManager.adjust_timezone is called
        actual_dataframe = MessageManager.adjust_date(expected_dataframe, date_to_adjust)

        # Then: the result sould be the same with expected one
        pd.testing.assert_frame_equal(actual_dataframe, expected_dataframe)
