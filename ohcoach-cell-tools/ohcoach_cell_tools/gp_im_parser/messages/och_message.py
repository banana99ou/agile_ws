from dataclasses import dataclass
from datetime import datetime

from ohcoach_cell_tools.gp_im_parser.messages.nmea_message import NmeaRMCMessage


@dataclass(init=True)
class OchMessage:
    date_time: str
    latitude: float
    longitude: float
    speed: float

    def __init__(self, nmea_rmc_message: NmeaRMCMessage):
        self.date_time = self.__get_datetime(
            utc_datestamp=nmea_rmc_message.utc_datestamp,
            utc_timestamp=nmea_rmc_message.utc_timestamp,
        )

        self.latitude = self.__get_latitude(
            msg_latitude_dms=nmea_rmc_message.latitude_dms,
            north_or_south=nmea_rmc_message.north_or_south,
        )
        self.longitude = self.__get_longitude(
            msg_longitude_dms=nmea_rmc_message.longitude_dms,
            east_or_west=nmea_rmc_message.east_or_west,
        )
        self.speed = self.__get_speed(
            msg_speed_knots=nmea_rmc_message.speed_knot,
        )

    def __get_datetime(self, utc_datestamp: str, utc_timestamp: str) -> str:
        dt_str = f"{utc_datestamp} {utc_timestamp}"
        dt = datetime.strptime(dt_str, "%d%m%y %H%M%S.%f")

        return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    def __get_latitude(self, msg_latitude_dms: str, north_or_south: str) -> float:
        degree = int(msg_latitude_dms[0 : (msg_latitude_dms.index(".") - 2)])
        minute = float(msg_latitude_dms[(msg_latitude_dms.index(".") - 2) :])

        latitude = degree + minute / 60.0
        if north_or_south == "S":
            latitude = -latitude

        return latitude

    def __get_longitude(self, msg_longitude_dms: str, east_or_west: str) -> float:
        degree = int(msg_longitude_dms[0 : (msg_longitude_dms.index(".") - 2)])
        minute = float(msg_longitude_dms[(msg_longitude_dms.index(".") - 2) :])

        longitude = degree + minute / 60.0
        if east_or_west == "W":
            longitude = -longitude

        return longitude

    def __get_speed(self, msg_speed_knots: str) -> float:
        return float(msg_speed_knots) * 1.852

    def is_valid(self) -> bool:
        return (
            self.date_time is not None
            and -90 <= self.latitude <= 90
            and -180 <= self.longitude <= 180
            and self.speed >= 0
        )

    @property
    def items(self) -> list:
        return [self.date_time, self.latitude, self.longitude, self.speed]
