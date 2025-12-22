from datetime import datetime
from typing import Tuple

import pandas as pd

from ohcoach_cell_tools.constants import (
    LABEL_DATETIME,
    LABEL_LATITUDE,
    LABEL_LONGITUDE,
    LABEL_SPEED,
)


class GpConverter:
    @staticmethod
    def split_datetime(dt: datetime) -> Tuple[str, str]:
        time_string = f"{dt.hour:0>2}{dt.minute:0>2}{dt.second:0>2}.{dt.microsecond // 10000:0>2}"
        date_string = f"{dt.day:0>2}{dt.month:0>2}{dt.year % 100:0>2}"

        return (time_string, date_string)

    @staticmethod
    def latitude_degree_to_nmea(latitude_degree: float) -> Tuple[str, str]:
        n_or_s = "N" if latitude_degree >= 0 else "S"
        latitude_degree = abs(latitude_degree)

        degree = int(latitude_degree)
        minute = (latitude_degree - degree) * 60
        nmea_latitude = f"{degree * 100 + minute:.5f}"

        return (nmea_latitude, n_or_s)

    @staticmethod
    def longitude_degree_to_nmea(longitude_degree: float) -> Tuple[str, str]:
        e_or_w = "E" if longitude_degree >= 0 else "W"
        longitude_degree = abs(longitude_degree)

        degree = int(longitude_degree)
        minute = (longitude_degree - degree) * 60
        nmea_longitude = f"{degree * 100 + minute:.5f}"

        return (nmea_longitude, e_or_w)

    @staticmethod
    def speed_kph_to_knots(speed_kph: float) -> str:
        return f"{speed_kph / 1.852:.3f}"

    @staticmethod
    def calculate_checksum(data_message: str) -> str:
        checksum = 0

        for elem in data_message:
            checksum = checksum ^ ord(elem)

        return hex(checksum).upper()[2:]

    @classmethod
    def encode_gps_row(cls, row: tuple) -> bytes:
        time_string, date_string = cls.split_datetime(getattr(row, LABEL_DATETIME))
        nmea_latitude, n_or_s = cls.latitude_degree_to_nmea(getattr(row, LABEL_LATITUDE))
        nmea_longitude, e_or_w = cls.longitude_degree_to_nmea(getattr(row, LABEL_LONGITUDE))
        speed_knot = cls.speed_kph_to_knots(getattr(row, LABEL_SPEED))

        crc_payload = "GPRMC,{},A,{},{},{},{},{},,{},,,A".format(
            time_string,
            nmea_latitude,
            n_or_s,
            nmea_longitude,
            e_or_w,
            speed_knot,
            date_string,
        )

        checksum = cls.calculate_checksum(crc_payload)

        return f"${crc_payload}*{checksum}".encode()

    @classmethod
    def encode_to_gp_format(cls, gps: pd.DataFrame) -> bytes:
        if gps.empty:
            raise Exception("GPS dataframe is empty")

        gps_copy = gps.copy()
        gps_copy[LABEL_DATETIME] = pd.to_datetime(gps_copy[LABEL_DATETIME], errors="coerce")
        gps = gps_copy.dropna()

        return b"start" + b"\r\n".join(
            cls.encode_gps_row(row) for row in gps.itertuples(index=False)
        )
