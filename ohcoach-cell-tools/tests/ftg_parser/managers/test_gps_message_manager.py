import pandas as pd
import pytest

from ohcoach_cell_tools.constants import GPS_EXPORT_COLUMNS
from ohcoach_cell_tools.ftg_parser.managers.gps_message_manager import GpsMessageManager

raw_gps_messages = [
    b"\xe4\x07\x02\x13j\xdb\t\x01P\xcf\x02\x13W\x00\x00\x00(\xb3\xa7\xdb'\x01\x00\x00\xde\x13\x02\x00|\x15\xec\x13\xd6\x06\x00\x00Pr\x00\x00\x00\x00\xd1\x00\xda\x00\xaf\x00\x06\x06)A",
    b"\xe4\x07\x02\x13t\xdb\t\x010\xfe\x02\x13W\x00\x00\x008]\xa7\xdb'\x01\x00\x00H\x0e\x02\x00\xcc\x10\x04\x10M\x07\x00\x00\x10l\x00\x00\x00\x00\xd1\x00\xda\x00\xaf\x00\x06\x06)A",
    b"\xe4\x07\x02\x13~\xdb\t\x01 T\x03\x13W\x00\x00\x00X\xb7\xa5\xdb'\x01\x00\x00Y\x0c\x02\x00\xac\rH\r\x08\x03\x00\x00\x10l\x00\x00\x00\x00\xd1\x00\xda\x00\xaf\x00\x06\x06)A",
    b"\xe4\x07\x02\x13\x88\xdb\t\x01@\xa2\x03\x13W\x00\x00\x00\x80\xe0\xa4\xdb'\x01\x00\x00m\x03\x02\x00T\x0bT\x0b\x05\x03\x00\x00Cq\x00\x00\x00\x00\xd1\x00\xda\x00\xaf\x00\x06\x06*A",
    b"\xe4\x07\x02\x13\x92\xdb\t\x010\xf8\x03\x13W\x00\x00\x00\xf0\xf1\xa5\xdb'\x01\x00\x00\x9a\xfb\x01\x00\xc4\t`\t\x1e\x01\x00\x00Cq\x00\x00\x00\x00\xd1\x00\xda\x00\xaf\x00\x06\x06*A",
]

expected_exported_rows = [
    b"\xe4\x07\x02\x13j\xdb\t\x01P\xcf\x02\x13W\x00\x00\x00(\xb3\xa7\xdb'\x01\x00\x00\xde\x13\x02\x00|\x15\xec\x13\xd6\x06\x00\x00Pr\x00\x00\x00\x00\xd1\x00\xda\x00\xaf\x00\x06\x06)A",
    b"\xe4\x07\x02\x13t\xdb\t\x010\xfe\x02\x13W\x00\x00\x008]\xa7\xdb'\x01\x00\x00H\x0e\x02\x00\xcc\x10\x04\x10M\x07\x00\x00\x10l\x00\x00\x00\x00\xd1\x00\xda\x00\xaf\x00\x06\x06)A",
    b"\xe4\x07\x02\x13~\xdb\t\x01 T\x03\x13W\x00\x00\x00X\xb7\xa5\xdb'\x01\x00\x00Y\x0c\x02\x00\xac\rH\r\x08\x03\x00\x00\x10l\x00\x00\x00\x00\xd1\x00\xda\x00\xaf\x00\x06\x06)A",
    b"\xe4\x07\x02\x13\x88\xdb\t\x01@\xa2\x03\x13W\x00\x00\x00\x80\xe0\xa4\xdb'\x01\x00\x00m\x03\x02\x00T\x0bT\x0b\x05\x03\x00\x00Cq\x00\x00\x00\x00\xd1\x00\xda\x00\xaf\x00\x06\x06*A",
    b"\xe4\x07\x02\x13\x92\xdb\t\x010\xf8\x03\x13W\x00\x00\x00\xf0\xf1\xa5\xdb'\x01\x00\x00\x9a\xfb\x01\x00\xc4\t`\t\x1e\x01\x00\x00Cq\x00\x00\x00\x00\xd1\x00\xda\x00\xaf\x00\x06\x06*A",
]


expected_exported_dataframe = pd.DataFrame(
    [
        [
            pd.Timestamp("2020-02-19 17:42:32.100000"),
            3739.81106,
            12707.00553,
            37.663517666666664,
            127.11675883333334,
            1.75,
            136.158,
            5.5,
            5.1,
            292.64,
            0.0,
            2.09,
            2.18,
            1.75,
            6,
            6,
            41,
            "A",
        ],
        [
            pd.Timestamp("2020-02-19 17:42:32.200000"),
            3739.81118,
            12707.00531,
            37.663519666666666,
            127.11675516666666,
            1.869,
            134.728,
            4.3,
            4.1,
            276.64,
            0.0,
            2.09,
            2.18,
            1.75,
            6,
            6,
            41,
            "A",
        ],
        [
            pd.Timestamp("2020-02-19 17:42:32.300000"),
            3739.8114,
            12707.00423,
            37.66352333333333,
            127.11673716666667,
            0.776,
            134.233,
            3.5,
            3.4,
            276.64,
            0.0,
            2.09,
            2.18,
            1.75,
            6,
            6,
            41,
            "A",
        ],
        [
            pd.Timestamp("2020-02-19 17:42:32.400000"),
            3739.8116,
            12707.00368,
            37.66352666666667,
            127.116728,
            0.773,
            131.949,
            2.9,
            2.9,
            289.95,
            0.0,
            2.09,
            2.18,
            1.75,
            6,
            6,
            42,
            "A",
        ],
        [
            pd.Timestamp("2020-02-19 17:42:32.500000"),
            3739.81182,
            12707.00438,
            37.663530333333334,
            127.11673966666666,
            0.286,
            129.946,
            2.5,
            2.4,
            289.95,
            0.0,
            2.09,
            2.18,
            1.75,
            6,
            6,
            42,
            "A",
        ],
    ],
    columns=GPS_EXPORT_COLUMNS,
).astype(
    dtype={
        "navigation_satellites": "uint8",
        "tracked_satellites": "uint8",
    }
)


@pytest.fixture
def gps_message_manager():
    message_manager = GpsMessageManager()

    for raw_message in raw_gps_messages:
        message_manager.add_message(raw_message)

    yield message_manager


class TestGpsMessageManager:
    def test_add_message(self):
        # Given: GpsMessageManager instance and raw gps messages
        gps_message_manager = GpsMessageManager()

        # When: GpsMessageManager.add_message is called on raw gps messages
        for raw_message in raw_gps_messages:
            gps_message_manager.add_message(raw_message)

        # Then: exported messages should eqaul as expected list of tuples
        assert gps_message_manager.messages == expected_exported_rows

    def test_export_dataframe(self, gps_message_manager):
        # When: GpsMessageManager.export_dataframe is called
        actual_dataframe = gps_message_manager.export_dataframe()

        # Then: exported dataframe should returned as expected
        pd.testing.assert_frame_equal(actual_dataframe, expected_exported_dataframe)

        # And: messages list should empty
        assert not gps_message_manager.messages

    def test_clear(self, gps_message_manager):
        # When: call clear method
        gps_message_manager.clear()

        # Then: messages list should be empty
        assert gps_message_manager.messages == []
