import struct

import numpy as np
import pandas as pd

from ohcoach_cell_tools.constants import BS_EXPORT_COLUMNS, BS_ORIGINAL_COLUMNS
from ohcoach_cell_tools.ftg_parser.utils.ftg_message_utils import date_time_utc_to_datetime, date_time_utc_to_datetime_for_debug

BATTERY_SCALING = 1e2
CELL_TEMPERATURE_SCALING = 1e2

BS_MESSAGE_DATA_TYPE = np.dtype(
    [
        ("date", "<I"),
        ("time_utc", "<i"),
        ("operation_time", "<I"),
        ("hr", "<H"),
        ("battery_scaled", "<H"),
        ("cell_temperature_scaled", "<h"),
        ("cell_state", "<H"),
        ("internal_hr", "<B"),
        ("wifi_rssi", "<b"),
        ("power_detect_voltage", "<B"),
        ("orientation", "<B"),
    ]
)


class BsMessage:
    bs_message_struct = struct.Struct("<IiIHHHHHH")
    message_length = bs_message_struct.size

    def __init__(self):
        pass

    @staticmethod
    def _get_message_dataframe(messages: list) -> pd.DataFrame:
        bs_message = b"".join(messages)
        bs_message_dataframe = pd.DataFrame(
            np.frombuffer(bs_message, dtype=BS_MESSAGE_DATA_TYPE), columns=BS_ORIGINAL_COLUMNS
        )

        return bs_message_dataframe

    @classmethod
    def get_calculated_dataframe(cls, messages: list) -> pd.DataFrame:
        dataframe = cls._get_message_dataframe(messages=messages)

        if dataframe.empty:
            return pd.DataFrame(columns=BS_EXPORT_COLUMNS)
        
        dataframe["datetime"] = dataframe[["date", "time_utc"]].apply(
            lambda x: date_time_utc_to_datetime(*x), axis=1
        )
        dataframe["battery"] = dataframe["battery_scaled"].apply(lambda x: x / BATTERY_SCALING)
        dataframe["cell_temperature"] = dataframe["cell_temperature_scaled"].apply(
            lambda x: x / CELL_TEMPERATURE_SCALING
        )
        dataframe["orientation"] = dataframe["orientation"].apply(lambda x: format(x, 'b'))

        dataframe.rename(columns={
            "battery_scaled": "voltage_mV",
            "cell_temperature_scaled": "current_mA",
        }, inplace=True)

        return dataframe[BS_EXPORT_COLUMNS]
