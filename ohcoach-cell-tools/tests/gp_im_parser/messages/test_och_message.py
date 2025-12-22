import pytest

from ohcoach_cell_tools.gp_im_parser.messages.nmea_message import NmeaRMCMessage
from ohcoach_cell_tools.gp_im_parser.messages.och_message import OchMessage

nmea_rmc_messages = [
    NmeaRMCMessage(
        nmea_message="$GPRMC,102603.50,A,3734.12258,N,12653.82030,E,1.301,,060722,,,A*74"
    ),
    NmeaRMCMessage(
        nmea_message="$GPRMC,102604.30,A,3734.10903,N,12653.82245,E,0.442,,060722,,,A*73"
    ),
    NmeaRMCMessage(
        nmea_message="$GPRMC,102606.80,A,3734.10404,N,12653.81257,E,0.943,,060722,,,A*7C"
    ),
    NmeaRMCMessage(
        nmea_message="$GPRMC,102607.40,A,3734.10423,N,12653.81570,E,0.864,,060722,,,A*72"
    ),
    NmeaRMCMessage(
        nmea_message="$GPRMC,102608.00,A,3734.10358,N,12653.81657,E,1.064,,060722,,,A*7D"
    ),
]

nmea_rmc_wrong_messages = [
    NmeaRMCMessage(
        nmea_message="$GPRMC,102603.50,A,3734.12258,N,19653.82030,E,1.301,,060722,,,A*74"
    ),
    NmeaRMCMessage(
        nmea_message="$GPRMC,102604.30,A,10734.10903,N,12653.82245,E,0.442,,060722,,,A*73"
    ),
    NmeaRMCMessage(
        nmea_message="$GPRMC,102606.80,A,3734.10404,N,12653.81257,E,-100,,060722,,,A*7C"
    ),
]


expected_och_message_items = [
    [
        "2022-07-06 10:26:03.500",
        37.56870966666666,
        126.89700500000001,
        2.409452,
    ],
    [
        "2022-07-06 10:26:04.300",
        37.56848383333333,
        126.89704083333334,
        0.8185840000000001,
    ],
    [
        "2022-07-06 10:26:06.800",
        37.56840066666667,
        126.89687616666667,
        1.746436,
    ],
    [
        "2022-07-06 10:26:07.400",
        37.568403833333335,
        126.89692833333334,
        1.600128,
    ],
    ["2022-07-06 10:26:08.000", 37.568393, 126.89694283333333, 1.9705280000000003],
]


class TestOchMessage:
    @pytest.mark.parametrize(
        "nmea_rmc_message, expected_date_time, expected_latitude, expected_longitude, expected_speed",
        [
            (
                nmea_rmc_messages[0],
                "2022-07-06 10:26:03.500",
                37.56870966666666,
                126.89700500000001,
                2.409452,
            ),
            (
                nmea_rmc_messages[1],
                "2022-07-06 10:26:04.300",
                37.56848383333333,
                126.89704083333334,
                0.8185840000000001,
            ),
            (
                nmea_rmc_messages[2],
                "2022-07-06 10:26:06.800",
                37.56840066666667,
                126.89687616666667,
                1.746436,
            ),
            (
                nmea_rmc_messages[3],
                "2022-07-06 10:26:07.400",
                37.568403833333335,
                126.89692833333334,
                1.600128,
            ),
            (
                nmea_rmc_messages[4],
                "2022-07-06 10:26:08.000",
                37.568393,
                126.89694283333333,
                1.9705280000000003,
            ),
        ],
    )
    def test_och_message_parsed(
        self,
        nmea_rmc_message,
        expected_date_time,
        expected_latitude,
        expected_longitude,
        expected_speed,
    ):
        # Given: parsed and create NmeaRMCMessage from nmea_message.message

        # When: parsed and created OchMessage from nmea_rmc_message
        och_message = OchMessage(nmea_rmc_message=nmea_rmc_message)

        # Then: date_time should be equal expected_date_time
        assert och_message.date_time == expected_date_time
        # AND: date_time should be equal expected_latitude
        assert och_message.latitude == expected_latitude
        # AND: date_time should be equal expected_longitude
        assert och_message.longitude == expected_longitude
        # AND: date_time should be equal expected_speed
        assert och_message.speed == expected_speed

    @pytest.mark.parametrize(
        "nmea_rmc_message",
        [
            (nmea_rmc_messages[0]),
            (nmea_rmc_messages[1]),
            (nmea_rmc_messages[2]),
            (nmea_rmc_messages[3]),
            (nmea_rmc_messages[4]),
        ],
    )
    def test_is_valid(self, nmea_rmc_message):
        # Given: parsed and created OchMessage from nmea_rmc_message
        och_message = OchMessage(nmea_rmc_message=nmea_rmc_message)

        # When: call is_valid method
        result = och_message.is_valid()

        # Then: result should be True
        assert result is True

    @pytest.mark.parametrize(
        "nmea_rmc_message",
        [
            (nmea_rmc_wrong_messages[0]),
            (nmea_rmc_wrong_messages[1]),
            (nmea_rmc_wrong_messages[2]),
        ],
    )
    def test_is_valid_fail(self, nmea_rmc_message):
        # Given: parsed and created OchMessage from nmea_rmc_message
        och_message = OchMessage(nmea_rmc_message=nmea_rmc_message)

        # When: call is_valid method
        result = och_message.is_valid()

        # Then: result should be False
        assert result is False

    @pytest.mark.parametrize(
        "nmea_rmc_message, expected_och_message_item",
        [
            (nmea_rmc_messages[0], expected_och_message_items[0]),
            (nmea_rmc_messages[1], expected_och_message_items[1]),
            (nmea_rmc_messages[2], expected_och_message_items[2]),
            (nmea_rmc_messages[3], expected_och_message_items[3]),
            (nmea_rmc_messages[4], expected_och_message_items[4]),
        ],
    )
    def test_items(self, nmea_rmc_message, expected_och_message_item):
        # Given: parsed and created OchMessage from nmea_rmc_message
        och_message = OchMessage(nmea_rmc_message=nmea_rmc_message)

        # When: call get items
        result = och_message.items

        # Then: result should be equal expected_och_message_item
        assert result == expected_och_message_item
