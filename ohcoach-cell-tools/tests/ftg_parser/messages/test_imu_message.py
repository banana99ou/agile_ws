import pandas as pd
import pytest

from ohcoach_cell_tools.constants import IMU_EXPORT_COLUMNS, IMU_ORIGINAL_COLUMNS
from ohcoach_cell_tools.ftg_parser.messages.imu_message import ImuMessage

imu_message_list = [
    b",\xc3\x06\x00\xffI\x00:\xf7]\xff\x9e\x00.\xff\xfbQ\x00\xb9\xff\x17\xff",
    b"\xf3\xc3\x06\x00\xffF\x00>\xf7`\xff\x9e\x00/\xff\xf9I\x00\xb1\xff\t\xff",
]

expected_converted_payload_list = [
    b",\xc3\x06\x00I\xff:\x00]\xf7\x9e\xff.\x00\xfb\xffQ\x00\xb9\xff\x17\xff",
    b"\xf3\xc3\x06\x00F\xff>\x00`\xf7\x9e\xff/\x00\xf9\xffI\x00\xb1\xff\t\xff",
]


imu_converted_message_list = [
    ImuMessage.convert_payload(
        bytearray(b",\xc3\x06\x00\xffI\x00:\xf7]\xff\x9e\x00.\xff\xfbQ\x00\xb9\xff\x17\xff")
    ),
    ImuMessage.convert_payload(
        bytearray(b"\xf3\xc3\x06\x00\xffF\x00>\xf7`\xff\x9e\x00/\xff\xf9I\x00\xb1\xff\t\xff")
    ),
]

expected_imu_message_dataframe_dtype = {
    "time_utc": "int32",
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


expected_imu_message_dataframe = pd.DataFrame(
    [
        [443180, -183, 58, -2211, -98, 46, -5, 81, -71, -233],
        [443379, -186, 62, -2208, -98, 47, -7, 73, -79, -247],
    ],
    columns=IMU_ORIGINAL_COLUMNS,
).astype(dtype=expected_imu_message_dataframe_dtype)

expected_imu_dataframe = pd.DataFrame(
    [
        [pd.Timestamp("1900-01-01 00:44:31.800000"), -183, 58, -2211, -98, 46, -5, 81, -71, -233],
        [pd.Timestamp("1900-01-01 00:44:33.790000"), -186, 62, -2208, -98, 47, -7, 73, -79, -247],
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


class TestImuMessage:
    @pytest.fixture(autouse=True)
    def set_up(self):
        self.imu_message = ImuMessage()

    def test_message_length(self):
        assert self.imu_message.message_length == 22

    def test_get_message_dataframe(self):
        pd.testing.assert_frame_equal(
            self.imu_message._get_message_dataframe(messages=imu_converted_message_list),
            expected_imu_message_dataframe,
        )

    def test_get_calculated_dataframe(self):
        dataframe = self.imu_message.get_calculated_dataframe(messages=imu_converted_message_list)
        print(dataframe.to_numpy())
        pd.testing.assert_frame_equal(dataframe, expected_imu_dataframe)

    def test_convert_payload(self):
        for i in range(len(imu_message_list)):
            payload = ImuMessage.convert_payload(bytearray(imu_message_list[i]))
            print(payload)
            assert payload == expected_converted_payload_list[i]
