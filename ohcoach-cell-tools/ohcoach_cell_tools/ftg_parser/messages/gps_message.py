import struct

import numpy as np
import pandas as pd

from ohcoach_cell_tools.constants import GPS_EXPORT_COLUMNS, GPS_ORIGINAL_COLUMNS
from ohcoach_cell_tools.ftg_parser.utils.ftg_message_utils import date_time_utc_to_datetime, date_time_utc_to_datetime_for_debug

COORDINATE_SCALING = 1e10
MINUTE_SCALING = 1e8
SECONDS_PER_MINUTE = 60

HEIGHT_SCALING = 1e3
H_ACC_SCALING = 1e3
V_ACC_SCALING = 1e3
SPEED_OF_GROUND_SCALING = 1e3
COURSE_ANGLE_SCALING = 1e2
V_VEL_SCALING = 1e3
PDOP_SCALING = 1e1
HDOP_SCALING = 1e2
VDOP_SCALING = 1e2
TDOP_SCALING = 1e2

LATITUDE = "latitude"
LONGITUDE = "longitude"
MINIMUM_LATITUDE = -90
MAXIMUM_LATITUDE = 90
MINIMUM_LONGITUDE = -180
MAXIMUM_LONGITUDE = 180


class GpsValueError(Exception):
    pass


GPS_MESSAGE_DATA_TYPE = np.dtype(
    [
        ("date", "<I"),
        ("time_utc", "<i"),
        ("gps_nmea_latitude", "<q"),
        ("gps_nmea_longitude", "<q"),
        ("height_scaled", "<i"),
        ("h_acc_scaled", "<H"),
        ("v_acc_scaled", "<H"),
        ("sog_scaled", "<i"),
        ("course_angle_scaled", "<H"),
        ("vertical_velocity_scaled", "<i"),
        ("filtered_sog_scaled", "<h"),
        ("filtered_vertical_velocity_scaled", "<h"),
        ("gps_valid", "<B"),
        ("pdop", "<B"),
        ("navigation_satellites", "<B"),
        ("tracked_satellites", "<B"),
        ("avg_cn0_scaled", "<B"),
        ("pos_mode_byte", "<c"),
    ]
)


class GpsMessage:
    gps_message_struct = struct.Struct("<IiqqiHHiHihhBBBBBc")
    message_length = gps_message_struct.size

    def __init__(self):
        pass

    @staticmethod
    def _get_message_dataframe(messages: list) -> pd.DataFrame:
        gps_message = b"".join(messages)
        gps_message_dataframe = pd.DataFrame(
            np.frombuffer(gps_message, dtype=GPS_MESSAGE_DATA_TYPE), columns=GPS_ORIGINAL_COLUMNS
        )

        return gps_message_dataframe

    @classmethod
    def get_calculated_dataframe(cls, messages: list) -> pd.DataFrame:
        dataframe = cls._get_message_dataframe(messages=messages)

        if dataframe.empty:
            return pd.DataFrame(columns=GPS_EXPORT_COLUMNS)

        dataframe["datetime"] = dataframe[["date", "time_utc"]].apply(
            lambda x: date_time_utc_to_datetime(*x), axis=1
        )
        dataframe["latitude"] = dataframe["gps_nmea_latitude"].apply(
            lambda x: cls.check_and_return_coordinate_value_within_range(
                coordinate_axis=LATITUDE,
                coordinate_value=cls.convert_nmea_to_decimal_degrees(x),
                lower_bound=MINIMUM_LATITUDE,
                upper_bound=MAXIMUM_LATITUDE,
            )
        )
        dataframe["longitude"] = dataframe["gps_nmea_longitude"].apply(
            lambda x: cls.check_and_return_coordinate_value_within_range(
                coordinate_axis=LONGITUDE,
                coordinate_value=cls.convert_nmea_to_decimal_degrees(x),
                lower_bound=MINIMUM_LONGITUDE,
                upper_bound=MAXIMUM_LONGITUDE,
            )
        )
        dataframe["nmea_latitude"] = dataframe["gps_nmea_latitude"].apply(
            lambda x: x / MINUTE_SCALING
        )
        dataframe["nmea_longitude"] = dataframe["gps_nmea_longitude"].apply(
            lambda x: x / MINUTE_SCALING
        )
        dataframe["speed"] = dataframe["sog_scaled"].apply(lambda x: x / SPEED_OF_GROUND_SCALING)
        dataframe["height"] = dataframe["height_scaled"].apply(lambda x: x / HEIGHT_SCALING)
        dataframe["h_acc"] = dataframe["h_acc_scaled"].apply(lambda x: x / H_ACC_SCALING)
        dataframe["v_acc"] = dataframe["v_acc_scaled"].apply(lambda x: x / V_ACC_SCALING)
        dataframe["course_angle"] = dataframe["course_angle_scaled"].apply(
            lambda x: x / COURSE_ANGLE_SCALING
        )
        dataframe["vertical_velocity"] = dataframe["vertical_velocity_scaled"].apply(
            lambda x: x / V_VEL_SCALING
        )
        dataframe["pdop"] = dataframe["pdop"].apply(lambda x: x / PDOP_SCALING)
        dataframe["filtered_sog"] = dataframe["filtered_sog_scaled"].apply(lambda x: x / SPEED_OF_GROUND_SCALING)
        dataframe["filtered_vertical_velocity"] = dataframe["filtered_vertical_velocity_scaled"].apply(lambda x: x / V_VEL_SCALING)
        dataframe["gps_valid"] = dataframe["gps_valid"].apply(lambda x: format(x, 'b'))
        dataframe["avg_cn0"] = dataframe["avg_cn0_scaled"].apply(lambda x: x)
        dataframe["pos_mode"] = dataframe["pos_mode_byte"].apply(lambda x: x.decode("utf-8"))

        return dataframe[GPS_EXPORT_COLUMNS]

    @staticmethod
    def convert_nmea_to_decimal_degrees(nmea_value) -> float:
        sign = 1 if nmea_value > 0 else -1

        degrees, minutes = divmod(abs(nmea_value), COORDINATE_SCALING)
        converted = degrees + minutes / (MINUTE_SCALING * SECONDS_PER_MINUTE)

        return sign * converted

    @staticmethod
    def check_and_return_coordinate_value_within_range(
        coordinate_axis: str, coordinate_value: float, lower_bound: int, upper_bound: int
    ) -> float:
        if lower_bound <= coordinate_value <= upper_bound:
            return coordinate_value
        raise GpsValueError(f"GPS {coordinate_axis} value is out of range {coordinate_value}")
