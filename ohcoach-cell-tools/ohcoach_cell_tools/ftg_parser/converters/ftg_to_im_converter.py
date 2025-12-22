import struct
from datetime import datetime

import pandas as pd

from ohcoach_cell_tools.constants import IMU_EXPORT_COLUMNS, LABEL_DATETIME


class ImConverter:
    start_token = b"BIAS..END\r\n\r\nstart20"

    initial_datetime_format = struct.Struct("<BBBBB")
    imu_row_format = struct.Struct(">BBhhhhhhhhh")
    imu_row_format_size = imu_row_format.size

    @classmethod
    def get_bytes_length(cls, imu: pd.DataFrame) -> int:
        return (
            len(cls.start_token)
            + cls.initial_datetime_format.size
            + len(imu) * cls.imu_row_format_size
        )

    @classmethod
    def encode_initial_datetime(cls, first_datetime: datetime) -> bytes:
        return cls.initial_datetime_format.pack(
            first_datetime.year % 100,
            first_datetime.month,
            first_datetime.day,
            first_datetime.hour,
            first_datetime.minute,
        )

    @classmethod
    def encode_imu_record(cls, row: tuple) -> bytes:
        dt = getattr(row, LABEL_DATETIME)

        return cls.imu_row_format.pack(
            dt.second,
            dt.microsecond // 10000,
            *tuple(getattr(row, field) for field in IMU_EXPORT_COLUMNS if field != LABEL_DATETIME),
        )

    @classmethod
    def encode_to_im_format(cls, imu: pd.DataFrame) -> bytearray:
        if imu.empty:
            raise Exception("IMU dataframe is empty")

        imu[LABEL_DATETIME] = pd.to_datetime(imu[LABEL_DATETIME], errors="coerce")
        imu = imu.dropna()

        result_byte_array = bytearray(b"\x00" * cls.get_bytes_length(imu))

        header = cls.start_token + cls.encode_initial_datetime(imu.loc[0][LABEL_DATETIME])
        result_byte_array[0 : len(header)] = header

        cursor = len(header)

        for row in imu.itertuples(index=False):
            row_bytes = cls.encode_imu_record(row)
            result_byte_array[cursor : cursor + cls.imu_row_format_size] = row_bytes
            cursor += cls.imu_row_format_size

        return result_byte_array
