import struct
import datetime
import numpy as np
import pandas as pd

from ohcoach_cell_tools.constants import HEADER_RIM, IMU_EXPORT_COLUMNS, IMU_ORIGINAL_COLUMNS
from ohcoach_cell_tools.ftg_parser.utils.ftg_message_utils import date_time_utc_to_datetime, date_time_utc_to_datetime_for_debug

IMU_MESSAGE_DATA_TYPE = np.dtype(
    [
        ("time_utc", "<i"),
        ("acc_x", "<h"),
        ("acc_y", "<h"),
        ("acc_z", "<h"),
        ("gyro_x", "<h"),
        ("gyro_y", "<h"),
        ("gyro_z", "<h"),
        ("magnet_x", "<h"),
        ("magnet_y", "<h"),
        ("magnet_z", "<h"),
    ]
)


class ImuMessage:
    time_utc_struct = struct.Struct("<i")
    accel_gyro_struct = struct.Struct(">hhhhhh")
    magnet_struct = struct.Struct("<hhh")
    message_length = time_utc_struct.size + accel_gyro_struct.size + magnet_struct.size

    def __init__(self):
        pass

    @classmethod
    def convert_payload(cls, payload: bytearray) -> bytes:
        accel_gyro_struct_start_idx = cls.time_utc_struct.size
        accel_gyro_struct_end_idx = accel_gyro_struct_start_idx + cls.accel_gyro_struct.size

        for i in range(accel_gyro_struct_start_idx, accel_gyro_struct_end_idx, 2):
            payload[i], payload[i + 1] = payload[i + 1], payload[i]

        return bytes(payload)

    @staticmethod
    def _get_message_dataframe(messages: list) -> pd.DataFrame:
        imu_message = b"".join(messages)
        imu_message_dataframe = pd.DataFrame(
            np.frombuffer(imu_message, dtype=IMU_MESSAGE_DATA_TYPE), columns=IMU_ORIGINAL_COLUMNS
        )

        return imu_message_dataframe

    @classmethod
    def get_calculated_dataframe(cls, messages: list) -> pd.DataFrame:
        dataframe = cls._get_message_dataframe(messages=messages)

        if dataframe.empty:
            return pd.DataFrame(columns=IMU_EXPORT_COLUMNS)

        dataframe["datetime"] = dataframe["time_utc"].apply(
            lambda x: date_time_utc_to_datetime(time_utc=x)
        )

        return dataframe[IMU_EXPORT_COLUMNS]


class Imu0x0EMessage:
    DTYPES = np.dtype(
        [
            ("date", "<I"),
            ("time_utc", "<I"),
            ("acc_scale", "<B"),
            ("gyro_scale", "<B"),
            ("mag_scale", "<B"),
            ("acc_x_init", "<h"),
            ("acc_y_init", "<h"),
            ("acc_z_init", "<h"),
            ("gyro_x_init", "<h"),
            ("gyro_y_init", "<h"),
            ("gyro_z_init", "<h"),
            ("mag_x_init", "<h"),
            ("mag_y_init", "<h"),
            ("mag_z_init", "<h"),
            ("acc_x_df_1", "<b"),
            ("acc_y_df_1", "<b"),
            ("acc_z_df_1", "<b"),
            ("gyro_x_df_1", "<b"),
            ("gyro_y_df_1", "<b"),
            ("gyro_z_df_1", "<b"),
            ("mag_x_df_1", "<b"),
            ("mag_y_df_1", "<b"),
            ("mag_z_df_1", "<b"),
            ("acc_x_df_2", "<b"),
            ("acc_y_df_2", "<b"),
            ("acc_z_df_2", "<b"),
            ("gyro_x_df_2", "<b"),
            ("gyro_y_df_2", "<b"),
            ("gyro_z_df_2", "<b"),
            ("mag_x_df_2", "<b"),
            ("mag_y_df_2", "<b"),
            ("mag_z_df_2", "<b"),
            ("acc_x_df_3", "<b"),
            ("acc_y_df_3", "<b"),
            ("acc_z_df_3", "<b"),
            ("gyro_x_df_3", "<b"),
            ("gyro_y_df_3", "<b"),
            ("gyro_z_df_3", "<b"),
            ("mag_x_df_3", "<b"),
            ("mag_y_df_3", "<b"),
            ("mag_z_df_3", "<b"),
            ("acc_x_df_4", "<b"),
            ("acc_y_df_4", "<b"),
            ("acc_z_df_4", "<b"),
            ("gyro_x_df_4", "<b"),
            ("gyro_y_df_4", "<b"),
            ("gyro_z_df_4", "<b"),
            ("mag_x_df_4", "<b"),
            ("mag_y_df_4", "<b"),
            ("mag_z_df_4", "<b"),
            ("acc_x_df_5", "<b"),
            ("acc_y_df_5", "<b"),
            ("acc_z_df_5", "<b"),
            ("gyro_x_df_5", "<b"),
            ("gyro_y_df_5", "<b"),
            ("gyro_z_df_5", "<b"),
            ("mag_x_df_5", "<b"),
            ("mag_y_df_5", "<b"),
            ("mag_z_df_5", "<b"),
            ("acc_x_df_6", "<b"),
            ("acc_y_df_6", "<b"),
            ("acc_z_df_6", "<b"),
            ("gyro_x_df_6", "<b"),
            ("gyro_y_df_6", "<b"),
            ("gyro_z_df_6", "<b"),
            ("mag_x_df_6", "<b"),
            ("mag_y_df_6", "<b"),
            ("mag_z_df_6", "<b"),
            ("acc_x_df_7", "<b"),
            ("acc_y_df_7", "<b"),
            ("acc_z_df_7", "<b"),
            ("gyro_x_df_7", "<b"),
            ("gyro_y_df_7", "<b"),
            ("gyro_z_df_7", "<b"),
            ("mag_x_df_7", "<b"),
            ("mag_y_df_7", "<b"),
            ("mag_z_df_7", "<b"),
            ("acc_x_df_8", "<b"),
            ("acc_y_df_8", "<b"),
            ("acc_z_df_8", "<b"),
            ("gyro_x_df_8", "<b"),
            ("gyro_y_df_8", "<b"),
            ("gyro_z_df_8", "<b"),
            ("mag_x_df_8", "<b"),
            ("mag_y_df_8", "<b"),
            ("mag_z_df_8", "<b"),
            ("acc_x_df_9", "<b"),
            ("acc_y_df_9", "<b"),
            ("acc_z_df_9", "<b"),
            ("gyro_x_df_9", "<b"),
            ("gyro_y_df_9", "<b"),
            ("gyro_z_df_9", "<b"),
            ("mag_x_df_9", "<b"),
            ("mag_y_df_9", "<b"),
            ("mag_z_df_9", "<b"),
        ]
    )
    message_length = DTYPES.itemsize

    def __init__(self):
        pass

    @classmethod
    def int_to_date(cls, date_int: int) -> datetime.date:
        year = date_int & 0xFFFF
        month = (date_int >> 16) & 0xFF
        day = (date_int >> 24) & 0xFF

        return datetime.date(year=year, month=month, day=day)

    @classmethod
    def int_to_time(cls, time_utc: int) -> datetime.time:
        microseconds = (time_utc % 100) * 10000
        seconds = (time_utc // 100) % 100
        minutes = (time_utc // 10000) % 100
        hours = (time_utc // 1000000) % 100

        return datetime.time(hour=hours, minute=minutes, second=seconds, microsecond=microseconds)

    @classmethod
    def translate(cls, row: pd.Series) -> list[dict]:
        acc_x, acc_y, acc_z = row["acc_x_init"], row["acc_y_init"], row["acc_z_init"]
        gyro_x, gyro_y, gyro_z = row["gyro_x_init"], row["gyro_y_init"], row["gyro_z_init"]
        mag_x, mag_y, mag_z = row["mag_x_init"], row["mag_y_init"], row["mag_z_init"]

        acc_scale = row["acc_scale"]
        gyro_scale = row["gyro_scale"]
        mag_scale = row["mag_scale"]

        t = datetime.datetime.combine(
            cls.int_to_date(row["date"]), cls.int_to_time(row["time_utc"])
        )

        translated_lists = []
        for i in range(0, 10):
            if i > 0:
                acc_x += row[f"acc_x_df_{i}"] * acc_scale
                acc_y += row[f"acc_y_df_{i}"] * acc_scale
                acc_z += row[f"acc_z_df_{i}"] * acc_scale
                gyro_x += row[f"gyro_x_df_{i}"] * gyro_scale
                gyro_y += row[f"gyro_y_df_{i}"] * gyro_scale
                gyro_z += row[f"gyro_z_df_{i}"] * gyro_scale
                mag_x += row[f"mag_x_df_{i}"] * mag_scale
                mag_y += row[f"mag_y_df_{i}"] * mag_scale
                mag_z += row[f"mag_z_df_{i}"] * mag_scale

            translated_lists.append(
                {
                    "datetime": t + pd.Timedelta(seconds=i * 0.01),
                    "acc_x": acc_x,
                    "acc_y": acc_y,
                    "acc_z": acc_z,
                    "gyro_x": gyro_x,
                    "gyro_y": gyro_y,
                    "gyro_z": gyro_z,
                    "magnet_x": mag_x,
                    "magnet_y": mag_y,
                    "magnet_z": mag_z,
                }
            )

        return translated_lists

    @classmethod
    def _get_message_dataframe(cls, messages: list) -> pd.DataFrame:
        imu_message = b"".join(messages)
        imu_message_dataframe = pd.DataFrame(
            np.frombuffer(imu_message, dtype=cls.DTYPES), columns=cls.DTYPES.names
        )

        return imu_message_dataframe

    @classmethod
    def get_calculated_dataframe(cls, messages: list) -> pd.DataFrame:
        dataframe = cls._get_message_dataframe(messages=messages)
        if dataframe.empty:
            return pd.DataFrame(columns=HEADER_RIM)

        translated = [cls.translate(row) for _, row in dataframe.iterrows()]
        flatten = [item for sublist in translated for item in sublist]
        dataframe = pd.DataFrame(flatten)
        dataframe = dataframe.dropna()
        return dataframe[HEADER_RIM]


class Imu0x0FMessage:
    DTYPES = np.dtype(
        [
            ("date", "<I"),
            ("time_utc", "<I"),
            ("acc_x_avg", "<h"),
            ("acc_y_avg", "<h"),
            ("acc_z_avg", "<h"),
            ("gyro_x_avg", "<h"),
            ("gyro_y_avg", "<h"),
            ("gyro_z_avg", "<h"),
            ("mag_x_avg", "<h"),
            ("mag_y_avg", "<h"),
            ("mag_z_avg", "<h"),
        ]
    )
    message_length = DTYPES.itemsize

    def __init__(self):
        pass

    @classmethod
    def int_to_date(cls, date_int: int) -> datetime.date:
        year = date_int & 0xFFFF
        month = (date_int >> 16) & 0xFF
        day = (date_int >> 24) & 0xFF

        return datetime.date(year=year, month=month, day=day)

    @classmethod
    def int_to_time(cls, time_utc: int) -> datetime.time:
        microseconds = (time_utc % 100) * 10000
        seconds = (time_utc // 100) % 100
        minutes = (time_utc // 10000) % 100
        hours = (time_utc // 1000000) % 100

        return datetime.time(hour=hours, minute=minutes, second=seconds, microsecond=microseconds)

    @classmethod
    def translate(cls, row: pd.Series) -> list[dict]:
        return [
            {
                "datetime": datetime.datetime.combine(
                    cls.int_to_date(row["date"]), cls.int_to_time(row["time_utc"])
                )
                + pd.Timedelta(seconds=0.05),
                "acc_x": row["acc_x_avg"],
                "acc_y": row["acc_y_avg"],
                "acc_z": row["acc_z_avg"],
                "gyro_x": row["gyro_x_avg"],
                "gyro_y": row["gyro_y_avg"],
                "gyro_z": row["gyro_z_avg"],
                "magnet_x": row["mag_x_avg"],
                "magnet_y": row["mag_y_avg"],
                "magnet_z": row["mag_z_avg"],
            }
        ]

    @classmethod
    def _get_message_dataframe(cls, messages: list) -> pd.DataFrame:
        imu_message = b"".join(messages)
        imu_message_dataframe = pd.DataFrame(
            np.frombuffer(imu_message, dtype=cls.DTYPES), columns=cls.DTYPES.names
        )

        return imu_message_dataframe

    @classmethod
    def get_calculated_dataframe(cls, messages: list) -> pd.DataFrame:
        dataframe = cls._get_message_dataframe(messages=messages)
        if dataframe.empty:
            return pd.DataFrame(columns=HEADER_RIM)

        translated = [cls.translate(row) for _, row in dataframe.iterrows()]
        flatten = [item for sublist in translated for item in sublist]
        dataframe = pd.DataFrame(flatten)
        dataframe = dataframe.dropna()
        return dataframe[HEADER_RIM]