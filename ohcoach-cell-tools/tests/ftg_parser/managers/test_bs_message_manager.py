import pandas as pd
import pytest

from ohcoach_cell_tools.constants import BS_EXPORT_COLUMNS
from ohcoach_cell_tools.ftg_parser.managers.bs_message_manager import CELL_STATE, BsMessageManager

raw_bs_messages = [
    b"\xe4\x07\x02\x13t\xdb\t\x01\x01\x00\x00\x00\x00\x00[\x01\xfe\xfe\x05\x00\x00\x00\x00\x00",
    b"\xe4\x07\x02\x13\xce\xdb\t\x01\x02\x00\x00\x00\x00\x00[\x01\xfe\xfe\x07\x00\x00\x00\x00\x00",
    b"\xe4\x07\x02\x132\xdc\t\x01\x03\x00\x00\x00\x00\x00[\x01\xfe\xfe\x00\x00\x00\x00\x00\x00",
    b"\xe4\x07\x02\x13\x96\xdc\t\x01\x04\x00\x00\x00\x00\x00[\x01\xfe\xfe\x01\x00\x00\x00\x00\x00",
    b"\xe4\x07\x02\x13\xfa\xdc\t\x01\x05\x00\x00\x00\x00\x00Z\x01\xfe\xfe\x02\x00\x00\x00\x00\x00",
]


expected_exported_rows = [
    b"\xe4\x07\x02\x13t\xdb\t\x01\x01\x00\x00\x00\x00\x00[\x01\xfe\xfe\x05\x00\x00\x00\x00\x00",
    b"\xe4\x07\x02\x13\xce\xdb\t\x01\x02\x00\x00\x00\x00\x00[\x01\xfe\xfe\x07\x00\x00\x00\x00\x00",
    b"\xe4\x07\x02\x132\xdc\t\x01\x03\x00\x00\x00\x00\x00[\x01\xfe\xfe\x00\x00\x00\x00\x00\x00",
    b"\xe4\x07\x02\x13\x96\xdc\t\x01\x04\x00\x00\x00\x00\x00[\x01\xfe\xfe\x01\x00\x00\x00\x00\x00",
    b"\xe4\x07\x02\x13\xfa\xdc\t\x01\x05\x00\x00\x00\x00\x00Z\x01\xfe\xfe\x02\x00\x00\x00\x00\x00",
]


expected_exported_dataframe = pd.DataFrame(
    [
        [pd.Timestamp("2020-02-19 17:42:32.200000"), 1, 0, 3.47, 652.78, 5, 0, 0],
        [pd.Timestamp("2020-02-19 17:42:33.100000"), 2, 0, 3.47, 652.78, 7, 0, 0],
        [pd.Timestamp("2020-02-19 17:42:34.100000"), 3, 0, 3.47, 652.78, 0, 0, 0],
        [pd.Timestamp("2020-02-19 17:42:35.100000"), 4, 0, 3.47, 652.78, 1, 0, 0],
        [pd.Timestamp("2020-02-19 17:42:36.100000"), 5, 0, 3.46, 652.78, 2, 0, 0],
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


@pytest.fixture
def bs_message_manager():
    message_manager = BsMessageManager()

    for raw_message in raw_bs_messages:
        message_manager.add_message(raw_message)

    yield message_manager


class TestBsMessageManager:
    def test_add_message(self):
        # Given: BsMessageManager instance and raw bs messages
        bs_message_manager = BsMessageManager()

        # When: BsMessageManager.add_message is called on raw bs messages
        for raw_message in raw_bs_messages:
            bs_message_manager.add_message(raw_message)

        # Then: exported messages should eqaul as expected list of tuples
        assert bs_message_manager.messages == expected_exported_rows

    def test_export_dataframe(self, bs_message_manager):
        # When: BsMessageManager.export_dataframe is called
        actual_dataframe = bs_message_manager.export_dataframe()

        # Then: exported dataframe should returned as expected
        pd.testing.assert_frame_equal(actual_dataframe, expected_exported_dataframe)

        # And: messages list should empty
        assert not bs_message_manager.messages

    def test_clear(self, bs_message_manager):
        # When: call clear method
        bs_message_manager.clear()

        # Then: messages list should be empty
        assert bs_message_manager.messages == []

    @pytest.mark.parametrize(
        "cell_states, check_result",
        [
            ((0, 0, 0, 0, 0), False),
            ((1, 1, 1, 1, 1), False),
            ((2, 2, 2, 2, 2), False),
            ((3, 3, 3, 3, 3), False),
            ((4, 4, 4, 4, 4), False),
            ((5, 5, 5, 5, 5), True),
            ((6, 6, 6, 6, 6), True),
            ((7, 7, 7, 7, 7), True),
            ((8, 8, 8, 8, 8), True),
            ((1, 7, 7, 7, 7), True),
            ((1, 1, 7, 7, 7), True),
            ((1, 1, 1, 7, 7), True),
            ((1, 1, 1, 1, 7), True),
            ((1, 7, 7, 7, 1), True),
            ((0, 1, 7, 7, 1), True),
            ((0, 1, 2, 7, 1), True),
        ],
    )
    def test_check_ble_connected(self, cell_states, check_result):
        # Given: a bs dataframe with replaced cell_state
        expected_exported_dataframe[CELL_STATE] = cell_states

        # Then: return of check_ble_connected method should be False
        assert BsMessageManager.check_ble_connected(expected_exported_dataframe) is check_result

    def test_check_ble_connected_when_rbs_is_empty(self):
        assert BsMessageManager.check_ble_connected(pd.DataFrame()) is False
