import pytest

from ohcoach_cell_tools.gp_im_parser.messages.nmea_message import (
    NmeaMessage,
    NmeaMessageType,
    NmeaRMCMessage,
)

gp_messages = [
    "$GPRMC,084756.80,A,3626.50740,N,12724.59262,E,1.854,96.04,290722,,,D*5B",
    "$GPRMC,084757.70,A,3626.50739,N,12724.59321,E,2.134,96.67,290722,,,D*54",
    "$GPRMC,084759.00,A,3626.50736,N,12724.59387,E,1.759,95.39,290722,,,D*58",
    "$GPRMC,084808.30,A,3626.50711,N,12724.59784,E,0.164,,290722,,,D*73",
    "$GPRMC,084809.50,A,3626.50707,N,12724.59790,E,0.097,,290722,,,D*7B",
    "$GPRMC,084851.70,A,3626.50717,N,12724.58963,E,0.867,109.41,290722,,,D*62",
]

nmea_messages = [
    NmeaMessage(gp_message=gp_messages[0]),
    NmeaMessage(gp_message=gp_messages[1]),
    NmeaMessage(gp_message=gp_messages[2]),
    NmeaMessage(gp_message=gp_messages[3]),
    NmeaMessage(gp_message=gp_messages[4]),
    NmeaMessage(gp_message=gp_messages[5]),
]

nmea_wrong_messages = [
    NmeaMessage(
        gp_message="GPRMC,084756.80,A,3626.50740,N,12724.59262,E,1.854,96.04,290722,,,D*5B"
    ),
    NmeaMessage(
        gp_message="$GPRMC,084757.70,N,3626.50739,N,12724.59321,E,2.134,96.67,290722,,,D*54"
    ),
    NmeaMessage(
        gp_message="$GPRMC,084759.00,A,3626.50736,N,12724.59387,E,1.759,95.39,290722,,,D*68"
    ),
]


class TestNmeaMessage:
    @pytest.mark.parametrize(
        "gp_message",
        [
            (gp_messages[0]),
            (gp_messages[1]),
            (gp_messages[2]),
            (gp_messages[3]),
            (gp_messages[4]),
            (gp_messages[5]),
        ],
    )
    def test_is_nmea_format(self, gp_message):
        # Given: parsed and create NmeaMessage from raw bytes of message
        nmea_message = NmeaMessage(gp_message=gp_message)

        # When: call is_nmea_format mehtod
        result = nmea_message.is_nmea_format()

        # Then: result should be True
        assert result is True

    def test_is_nmea_format_fail(self):
        gp_message = "$GARMC,084756.80,A,3626.50740,N,12724.59262,E,1.854,96.04,290722,,,D*5B"
        # Given: parsed and create NmeaMessage from raw bytes of message
        nmea_message = NmeaMessage(gp_message=gp_message)

        # When: call is_nmea_format mehtod
        result = nmea_message.is_nmea_format()

        # Then: result should be False
        assert result is False

    @pytest.mark.parametrize(
        "gp_message",
        [
            (gp_messages[0]),
            (gp_messages[1]),
            (gp_messages[2]),
            (gp_messages[3]),
            (gp_messages[4]),
            (gp_messages[5]),
        ],
    )
    def test_get_type(self, gp_message):
        # Given: parsed and create NmeaMessage from raw bytes of message
        nmea_message = NmeaMessage(gp_message=gp_message)

        # When: call get type
        result = nmea_message.type

        # Then: result should be equal NmeaMessageType.RMC
        assert result == NmeaMessageType.RMC


class TestNmeaRMCMessage:
    @pytest.mark.parametrize(
        "nmea_message, expected_header, expected_utc_timestamp, expected_active_or_void, expected_latitude_dms, expected_north_or_south, expected_longitude_dms, expected_east_or_west, expected_speed_knot, expected_utc_datestamp, expected_checksum",
        [
            (
                nmea_messages[0],
                "$GPRMC",
                "084756.80",
                "A",
                "3626.50740",
                "N",
                "12724.59262",
                "E",
                "1.854",
                "290722",
                "5B",
            ),
            (
                nmea_messages[1],
                "$GPRMC",
                "084757.70",
                "A",
                "3626.50739",
                "N",
                "12724.59321",
                "E",
                "2.134",
                "290722",
                "54",
            ),
            (
                nmea_messages[2],
                "$GPRMC",
                "084759.00",
                "A",
                "3626.50736",
                "N",
                "12724.59387",
                "E",
                "1.759",
                "290722",
                "58",
            ),
            (
                nmea_messages[3],
                "$GPRMC",
                "084808.30",
                "A",
                "3626.50711",
                "N",
                "12724.59784",
                "E",
                "0.164",
                "290722",
                "73",
            ),
            (
                nmea_messages[4],
                "$GPRMC",
                "084809.50",
                "A",
                "3626.50707",
                "N",
                "12724.59790",
                "E",
                "0.097",
                "290722",
                "7B",
            ),
            (
                nmea_messages[5],
                "$GPRMC",
                "084851.70",
                "A",
                "3626.50717",
                "N",
                "12724.58963",
                "E",
                "0.867",
                "290722",
                "62",
            ),
        ],
    )
    def test_nmea_rmc_message_parsed(
        self,
        nmea_message,
        expected_header,
        expected_utc_timestamp,
        expected_active_or_void,
        expected_latitude_dms,
        expected_north_or_south,
        expected_longitude_dms,
        expected_east_or_west,
        expected_speed_knot,
        expected_utc_datestamp,
        expected_checksum,
    ):
        # Given: parsed and created NmeaMessage

        # When: call NmeaRMCMessage
        nmea_rmc_message = NmeaRMCMessage(nmea_message=nmea_message.message)

        # Then: header should be equal expected_header
        assert nmea_rmc_message.header == expected_header
        # AND: utc_timestamp should be equal expected_utc_timestamp
        assert nmea_rmc_message.utc_timestamp == expected_utc_timestamp
        # AND: active_or_void should be equal expected_active_or_void
        assert nmea_rmc_message.active_or_void == expected_active_or_void
        # AND: latitude_dms should be equal expected_latitude_dms
        assert nmea_rmc_message.latitude_dms == expected_latitude_dms
        # AND: north_or_south should be equal expected_north_or_south
        assert nmea_rmc_message.north_or_south == expected_north_or_south
        # AND: longitude_dms should be equal expected_longitude_dms
        assert nmea_rmc_message.longitude_dms == expected_longitude_dms
        # AND: east_or_west should be equal expected_east_or_west
        assert nmea_rmc_message.east_or_west == expected_east_or_west
        # AND: speed_knot should be equal expected_speed_knot
        assert nmea_rmc_message.speed_knot == expected_speed_knot
        # AND: utc_datestamp should be equal expected_utc_datestamp
        assert nmea_rmc_message.utc_datestamp == expected_utc_datestamp
        # AND: checksum should be equal expected_checksum
        assert nmea_rmc_message.checksum == expected_checksum

    @pytest.mark.parametrize(
        "nmea_message",
        [
            (nmea_messages[0]),
            (nmea_messages[1]),
            (nmea_messages[2]),
            (nmea_messages[3]),
            (nmea_messages[4]),
            (nmea_messages[5]),
        ],
    )
    def test_is_valid(self, nmea_message):
        # Given: parsed and create NmeaRMCMessage from nmea_message.message
        nmea_rmc_message = NmeaRMCMessage(nmea_message=nmea_message.message)

        # When: call is_valid method
        result = nmea_rmc_message.is_valid()

        # Then: result should be True
        assert result is True

    @pytest.mark.parametrize(
        "nmea_message",
        [
            (nmea_wrong_messages[0]),
            (nmea_wrong_messages[1]),
            (nmea_wrong_messages[2]),
        ],
    )
    def test_is_valid_fail(self, nmea_message):
        # Given: parsed and create NmeaRMCMessage from nmea_message.message
        nmea_rmc_message = NmeaRMCMessage(nmea_message=nmea_message.message)

        # When: call is_valid method
        result = nmea_rmc_message.is_valid()

        # Then: result should be False
        assert result is False
