import pandas as pd
import pytest

from ohcoach_cell_tools.constants import BS_EXPORT_COLUMNS, BS_ORIGINAL_COLUMNS
from ohcoach_cell_tools.ftg_parser.messages.bs_message import BsMessage

bs_message_list = [
    b"\xe7\x07\x02\x02@\xc3\x06\x00\x01\x00\x00\x00\x00\x00\xa2\x01\x00\x00\x01\x00\x00\x00\x00\x00",
    b"\xe7\x07\x02\x02\xac\xca\x06\x00\x14\x00\x00\x00\x00\x00\xa2\x01\x00\x00\x01\x00\x00\x00\x00\x00",
]


expected_bs_message_dataframe_dtype = {
    "date": "uint32",
    "time_utc": "int32",
    "operation_time": "uint32",
    "hr": "uint16",
    "battery_scaled": "uint16",
    "cell_temperature_scaled": "uint16",
    "cell_state": "uint16",
    "reserve_2": "uint16",
    "reserve_3": "uint16",
}


expected_bs_message_dataframe = pd.DataFrame(
    [
        [33687527, 443200, 1, 0, 418, 0, 1, 0, 0],
        [33687527, 445100, 20, 0, 418, 0, 1, 0, 0],
    ],
    columns=BS_ORIGINAL_COLUMNS,
).astype(dtype=expected_bs_message_dataframe_dtype)


expected_bs_dataframe = pd.DataFrame(
    [
        [pd.Timestamp("2023-02-02 00:44:32"), 1, 0, 4.18, 0.0, 1, 0, 0],
        [pd.Timestamp("2023-02-02 00:44:51"), 20, 0, 4.18, 0.0, 1, 0, 0],
    ],
    columns=BS_EXPORT_COLUMNS,
).astype(
    dtype={
        "operation_time": "uint32",
        "hr": "uint16",
        "cell_state": "uint16",
        "reserve_2": "uint16",
        "reserve_3": "uint16",
    }
)


class TestBsMessage:
    @pytest.fixture(autouse=True)
    def set_up(self):
        self.bs_message = BsMessage()

    def test_message_length(self):
        assert self.bs_message.message_length == 24

    def test_get_message_dataframe(self):
        pd.testing.assert_frame_equal(
            self.bs_message._get_message_dataframe(messages=bs_message_list),
            expected_bs_message_dataframe,
        )

    def test_get_calculated_dataframe(self):
        dataframe = self.bs_message.get_calculated_dataframe(messages=bs_message_list)

        pd.testing.assert_frame_equal(dataframe, expected_bs_dataframe)
