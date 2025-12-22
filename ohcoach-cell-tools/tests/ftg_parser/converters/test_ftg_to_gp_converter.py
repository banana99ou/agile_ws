from datetime import datetime

import pandas as pd
import pytest

from ohcoach_cell_tools.constants import HEADER_RGP
from ohcoach_cell_tools.ftg_parser.converters.ftg_to_gp_converter import GpConverter
from tests.ftg_parser.converters.conversion_test_data import encoded_gps_result, sample_gps_rows

gps_dataframe = pd.DataFrame(sample_gps_rows, columns=HEADER_RGP)


class TestGpConverter:
    def test_split_datetime(self):
        # Given: a datetime
        dt = datetime(2022, 2, 7, 18, 12, 56, 200000)

        # When: call split_datetime on the datetime
        actual_time_string, actual_date_string = GpConverter.split_datetime(dt)

        # Then: time_string and date_string should match
        expected_time_string = "181256.20"
        expected_date_string = "070222"

        assert actual_time_string == expected_time_string
        assert actual_date_string == expected_date_string

    @pytest.mark.parametrize(
        "latitude_degree, expected_latitude_nmea, expected_n_or_s",
        [
            (37.40887433333333, "3724.53246", "N"),
            (-37.40887433333333, "3724.53246", "S"),
            (37.388101, "3723.28606", "N"),
            (-37.388101, "3723.28606", "S"),
            (37.388102333333336, "3723.28614", "N"),
            (-37.388102333333336, "3723.28614", "S"),
        ],
    )
    def test_latitude_degree_to_nmea(
        self, latitude_degree, expected_latitude_nmea, expected_n_or_s
    ):
        # When: call latitude_degree_to_nmea on latitude_degree
        actual_latitude_nmea, actual_n_or_s = GpConverter.latitude_degree_to_nmea(latitude_degree)

        # Then: latitude_nmea and n_or_s should match
        assert actual_latitude_nmea == expected_latitude_nmea
        assert actual_n_or_s == expected_n_or_s

    @pytest.mark.parametrize(
        "longitude_degree, expected_longitude_nmea, expected_e_or_w",
        [
            (126.69736833333333, "12641.84210", "E"),
            (-126.69736833333333, "12641.84210", "W"),
            (126.98837933333333, "12659.30276", "E"),
            (-126.98837933333333, "12659.30276", "W"),
            (126.9883795, "12659.30277", "E"),
            (-126.9883795, "12659.30277", "W"),
        ],
    )
    def test_longitude_degree_to_nmea(
        self, longitude_degree, expected_longitude_nmea, expected_e_or_w
    ):
        # When: call longitude_degree_to_nmea on longitude_degree
        actual_longitude_nmea, actual_e_or_w = GpConverter.longitude_degree_to_nmea(
            longitude_degree
        )

        # Then: longitude_nmea and e_or_w should match
        assert actual_longitude_nmea == expected_longitude_nmea
        assert actual_e_or_w == expected_e_or_w

    def test_message_to_speed_knots(self):
        # Given: speed in km/h
        speed_in_kph = 12.123

        # When: call speed_kph_to_knots on the speed
        actual_knots = GpConverter.speed_kph_to_knots(speed_in_kph)

        # Then: the converted speed match
        assert actual_knots == "6.546"

    def test_calculate_checksum(self):
        # Given: a full RMC GPS message
        full_msg = "$GPRMC,004624.30,A,3730.68848,N,12652.33544,E,0.180,,040122,,,A*71"

        # When: call calculate_checksum on string between $ and *
        actual_checksum = GpConverter.calculate_checksum(
            full_msg[full_msg.find("$") + 1 : full_msg.find("*")]
        )

        # Then: checksum should match
        assert actual_checksum == full_msg[-2:]

    def test_encode_gps_row(self):
        expected_encoded_gps_row = (
            b"$GPRMC,174232.10,A,3739.81106,N,12707.00553,E,0.945,,190220,,,A*70"
        )

        # When: call encode_gps_row on the fisrt row of gps_dataframe
        actual_encoded_gps_row = GpConverter.encode_gps_row(gps_dataframe.loc[0])

        # Then: the result should be equal to the expected string
        assert actual_encoded_gps_row == expected_encoded_gps_row

    def test_encode_to_gp_format(self):
        # When: call encode_to_gp_format on gps_dataframe
        actual_gp_file_content = GpConverter.encode_to_gp_format(gps_dataframe)

        # Then: the result should be equal to the expected gp string
        assert actual_gp_file_content == encoded_gps_result
