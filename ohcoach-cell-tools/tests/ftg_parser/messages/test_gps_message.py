import pandas as pd
import pytest

from ohcoach_cell_tools.constants import GPS_EXPORT_COLUMNS, GPS_ORIGINAL_COLUMNS
from ohcoach_cell_tools.ftg_parser.messages.gps_message import GpsMessage, GpsValueError

gps_message_list = [
    b"\xe7\x07\x02\x02,\xc3\x06\x00x\xfd\x83\xf5Q\x00\x00\x00p\x0f %D\x01\x00\x00\xfa\xbd\x00\x00\xa0\x0f$\x13N\x00\x00\x00\x00\x00\xf9\xff\xff\xff\x8a\x00\xa2\x00q\x00\x06\x0f'A",
    b"\xe7\x07\x02\x02\xea\xc3\x06\x00\x80\xd2\x83\xf5Q\x00\x00\x00\x806 %D\x01\x00\x00\x85\xbe\x00\x00T\x0bt\x0e5\x00\x00\x00\x00\x00\xff\xff\xff\xff\x8a\x00\xa2\x00q\x00\x06\x0f'A",
]


expected_gps_message_dataframe_dtype = {
    "date": "uint32",
    "time_utc": "int32",
    "gps_nmea_latitude": "int64",
    "gps_nmea_longitude": "int64",
    "height_scaled": "uint32",
    "h_acc_scaled": "uint16",
    "v_acc_scaled": "uint16",
    "sog_scaled": "int32",
    "course_angle_scaled": "uint16",
    "vertical_velocity_scaled": "int32",
    "hdop_scaled": "uint16",
    "vdop_scaled": "uint16",
    "tdop_scaled": "uint16",
    "navigation_satellites": "uint8",
    "tracked_satellites": "uint8",
    "avg_cn0_scaled": "uint8",
    "pos_mode_byte": "object",
}


expected_gps_message_dataframe = pd.DataFrame(
    [
        [
            33687527,
            443180,
            352011419000,
            1392192262000,
            48634,
            4000,
            4900,
            78,
            0,
            -7,
            138,
            162,
            113,
            6,
            15,
            39,
            b"A",
        ],
        [
            33687527,
            443370,
            352011408000,
            1392192272000,
            48773,
            2900,
            3700,
            53,
            0,
            -1,
            138,
            162,
            113,
            6,
            15,
            39,
            b"A",
        ],
    ],
    columns=GPS_ORIGINAL_COLUMNS,
).astype(dtype=expected_gps_message_dataframe_dtype)


expected_gps_dataframe = pd.DataFrame(
    [
        [
            pd.Timestamp("2023-02-02 00:44:31.800000"),
            3520.11419,
            13921.92262,
            35.3352365,
            139.365377,
            0.078,
            48.634,
            4.0,
            4.9,
            0.0,
            -0.007,
            1.38,
            1.62,
            1.13,
            6,
            15,
            39,
            "A",
        ],
        [
            pd.Timestamp("2023-02-02 00:44:33.700000"),
            3520.11408,
            13921.92272,
            35.335234666666665,
            139.36537866666666,
            0.053,
            48.773,
            2.9,
            3.7,
            0.0,
            -0.001,
            1.38,
            1.62,
            1.13,
            6,
            15,
            39,
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


class TestGpsMessage:
    @pytest.fixture(autouse=True)
    def set_up(self):
        self.gps_message = GpsMessage()

    def test_message_length(self):
        assert self.gps_message.message_length == 52

    def test_get_message_dataframe(self):
        pd.testing.assert_frame_equal(
            self.gps_message._get_message_dataframe(messages=gps_message_list),
            expected_gps_message_dataframe,
        )

    """
    examples:
    3724.53246,N,12641.84210,E
    lat= 37.40887433333333, lon= 126.69736833333333

    3724.53246,S,12641.84210,W
    lat= -37.40887433333333, lon= -126.69736833333333

    3723.28606,N,12659.30276,E
    lat= 37.388101, lon= 126.98837933333333

    3723.28606,S,12659.30276,W
    lat= -37.388101, lon= -126.98837933333333

    3723.28614,N,12659.30277,E
    lat= 37.388102333333336, lon= 126.9883795

    3723.28614,S,12659.30277,W
    lat= -37.388102333333336, lon= -126.9883795

    3723.28651,N,12659.30284,E
    lat= 37.3881085, lon= 126.98838066666667

    3723.28651,S,12659.30284,W
    lat= -37.3881085, lon= -126.98838066666667

    3723.27819,N,12659.30087,E
    lat= 37.38796983333334, lon= 126.98834783333334

    3723.27819,S,12659.30087,W
    lat= -37.38796983333334, lon= -126.98834783333334
    """

    @pytest.mark.parametrize(
        "nmea_format, decimal_format",
        [
            (372453246000, 37.40887433333333),
            (1264184210000, 126.69736833333333),
            (-372453246000, -37.40887433333333),
            (-1264184210000, -126.69736833333333),
            (372328606000, 37.388101),
            (1265930276000, 126.98837933333333),
            (-372328606000, -37.388101),
            (-1265930276000, -126.98837933333333),
            (372328614000, 37.388102333333336),
            (1265930277000, 126.9883795),
            (-372328614000, -37.388102333333336),
            (-1265930277000, -126.9883795),
            (372328651000, 37.3881085),
            (1265930284000, 126.98838066666667),
            (-372328651000, -37.3881085),
            (-1265930284000, -126.98838066666667),
            (372327819000, 37.38796983333334),
            (1265930087000, 126.98834783333334),
            (-372327819000, -37.38796983333334),
            (-1265930087000, -126.98834783333334),
        ],
    )
    def test_convert_nmea_to_decimal_degrees(self, nmea_format, decimal_format):
        # Given: nmea_format in dd.mmmmmmm * 10 ^ 7 format

        # When: call convert_nmea_to_dicimal_degreees static method on nmea_format
        actual_decimal = self.gps_message.convert_nmea_to_decimal_degrees(nmea_format)

        # Then: the result matches
        assert actual_decimal == decimal_format

    def test_coordinate_validity_latitude_out_of_range(self):
        expected = "GPS latitude value is out of range 101.99999"

        with pytest.raises(GpsValueError) as error:
            # When: call check_coordinate_validity
            # Then: error_message equal expected
            self.gps_message._check_and_return_coordinate_value_within_range(
                "latitude", 101.99999, -90, 90
            )

        assert str(error.value) == expected

    def test_coordinate_validity_longitude_out_of_range(self):
        expected = "GPS longitude value is out of range -194577604.0931995"

        with pytest.raises(GpsValueError) as error:
            # When: call check_coordinate_validity
            # Then: error_message equal expected
            self.gps_message._check_and_return_coordinate_value_within_range(
                "longitude", -194577604.0931995, -180, 180
            )

        assert str(error.value) == expected

    def test_get_calculated_dataframe(self):
        dataframe = self.gps_message.get_calculated_dataframe(messages=gps_message_list)

        pd.testing.assert_frame_equal(dataframe, expected_gps_dataframe)
