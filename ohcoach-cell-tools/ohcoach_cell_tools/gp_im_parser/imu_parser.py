from datetime import datetime, timedelta

import pandas as pd

from ohcoach_cell_tools.common.logger import Logger
from ohcoach_cell_tools.constants import (
    BYTES_ACC,
    BYTES_GYRO,
    BYTES_MAGNET,
    FORMAT_DATETIME_SSFF,
    FORMAT_INITIAL_DATETIME_YYMMDDHHII,
    HEADER_RIM,
)
from ohcoach_cell_tools.gp_im_parser.utils.dataframe_utils import get_processed_dataframe
from ohcoach_cell_tools.gp_im_parser.utils.gp_im_data_utils import ImuData


class DateTimeExecption(Exception):
    pass


class ImuParser:
    _logger = Logger("ImuParser")

    def __init__(self, imu_data: ImuData):
        self.imu_data = imu_data
        self.format_initial_datetime = FORMAT_INITIAL_DATETIME_YYMMDDHHII
        self.format_datetime = FORMAT_DATETIME_SSFF
        self.initial_data_packet_len = len(self.format_initial_datetime) + 2  # len(b"20") == 2
        self.data_packet_len = len(self.format_datetime) + BYTES_ACC + BYTES_GYRO + BYTES_MAGNET

    def __byte_to_16int(self, byte: list) -> int:
        return int.from_bytes(byte, byteorder="big", signed=True)

    # 계측 날짜 파싱 함수, hex 데이터 초반부분에서 명시된다
    def __get_measured_date_time(self, measured_data: list) -> datetime:
        # year, month, day가 0이면 PHP처럼 -1 취급
        if not (measured_data[2] and measured_data[3] and measured_data[4]):
            return datetime(2000 - 1, 12 - 1, 31 - 1, 0, 0, 0)

        return datetime(
            int(measured_data[2] + 2000),
            int(measured_data[3]),
            int(measured_data[4]),
            int(measured_data[5]),
            int(measured_data[6]),
        )

    def __get_parsed_date_time(self, prev: datetime, stream: list) -> datetime:
        date_time = datetime(
            prev.year,
            prev.month,
            prev.day,
            prev.hour,
            prev.minute,
            int(stream[0]),
            microsecond=1000 * int(int(stream[1]) * (1000 / self.imu_data.frequency)),
        )
        if date_time.second < prev.second:
            date_time = date_time + timedelta(minutes=1)

        self.__time_difference_error_filter(prev, date_time)

        return date_time

    def __time_difference_error_filter(self, prev: datetime, current: datetime):
        diff_seconds = current - prev

        if diff_seconds.microseconds > 1000000:  # over 1 second
            raise DateTimeExecption(
                f"{current} {prev} second diffrence is larger than\
                    1 second VALUE(microsecond) - {diff_seconds}"
            )
        elif diff_seconds.total_seconds() < 0:  # reverse timeline
            raise DateTimeExecption(
                f"{current} {prev} second diffrence is lesser than\
                    0 second VALUE(microsecond) - {diff_seconds}"
            )

    def __get_parsed_acc_gyro_magnet_data(self, stream: list) -> list:
        """
        acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z, magnet_x, magnet_y, magnet_z,
        """
        idx = len(self.format_datetime)
        acc_data = stream[idx : idx + BYTES_ACC + BYTES_GYRO + BYTES_MAGNET]
        gyro_data = stream[idx + BYTES_ACC : idx + BYTES_ACC + BYTES_GYRO]
        magnet_data = stream[
            idx + BYTES_ACC + BYTES_GYRO : idx + BYTES_ACC + BYTES_GYRO + BYTES_MAGNET
        ]
        return [
            self.__byte_to_16int(acc_data[0:2]),
            self.__byte_to_16int(acc_data[2:4]),
            self.__byte_to_16int(acc_data[4:6]),
            self.__byte_to_16int(gyro_data[0:2]),
            self.__byte_to_16int(gyro_data[2:4]),
            self.__byte_to_16int(gyro_data[4:6]),
            self.__byte_to_16int(magnet_data[0:2]),
            self.__byte_to_16int(magnet_data[2:4]),
            self.__byte_to_16int(magnet_data[4:6]),
        ]

    def __get_parsed_hex_data(self, prev: list, stream: list) -> list:
        date_time = self.__get_parsed_date_time(prev=prev[0], stream=stream)
        acc_gyro_magnet_data = self.__get_parsed_acc_gyro_magnet_data(stream)

        return [date_time, *acc_gyro_magnet_data]

    def __get_splitted_stream(self) -> bytes:
        stream = self.imu_data.im_stream

        # production bias, calibration bias 제거
        if self.imu_data.device_version > "2X" and b"BIAS" in stream:
            tokens = stream.split(b"END\r\n\r\nstart20")
            return b"20" + tokens[-1]
        return stream

    def __get_df_list(self, start_idx: int, stream: bytes, prev_data: list) -> list:
        df_list = []
        for idx in range(start_idx, len(stream), self.data_packet_len):
            try:
                chunk = stream[idx : idx + self.data_packet_len]
                chunk_list = [int(c) for c in chunk]
                parsed_hex_data = self.__get_parsed_hex_data(prev=prev_data, stream=chunk_list)

                if parsed_hex_data and parsed_hex_data[0] != datetime(1970, 1, 1):
                    df_list.append(parsed_hex_data)
                prev_data = parsed_hex_data
            except DateTimeExecption as e:
                self._logger.error(e)
            except Exception:
                pass

        return df_list

    def __get_stream_df(self) -> pd.DataFrame:
        stream = self.__get_splitted_stream()

        try:
            #  First line : b"20" + measured date_time
            measured_data = [int(c) for c in stream[0 : self.initial_data_packet_len]]
            measured_date_time = self.__get_measured_date_time(measured_data=measured_data)

        except Exception:
            return pd.DataFrame(columns=HEADER_RIM)

        start_idx = self.initial_data_packet_len
        prev_data = [measured_date_time]

        df_list = self.__get_df_list(start_idx, stream, prev_data)

        return pd.DataFrame(df_list, columns=HEADER_RIM)

    def run(self) -> pd.DataFrame:
        stream_df = self.__get_stream_df()

        return get_processed_dataframe(df=stream_df)
