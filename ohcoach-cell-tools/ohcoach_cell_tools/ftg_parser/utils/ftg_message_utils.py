from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from ohcoach_cell_tools.constants import LABEL_DATETIME, LABEL_POS_MODE, LABEL_SPEED


def date_time_utc_to_datetime(date: Optional[int] = None, time_utc: int = 0) -> datetime:
    year, month, day = 1900, 1, 1

    if date:
        year = date & 0xFFFF
        month = (date >> 16) & 0xFF
        day = (date >> 24) & 0xFF

    rest, micro = divmod(time_utc, 100)
    rest, seconds = divmod(rest, 100)
    hours, minutes = divmod(rest, 100)
    return datetime(year, month, day, hours, minutes, seconds, micro * 10000)

def date_time_utc_to_datetime_for_debug(date: Optional[int] = None, time_utc: int = 0) -> str:
    year, month, day = 1900, 1, 1

    if date:
        year = date & 0xFFFF
        month = (date >> 16) & 0xFF
        day = (date >> 24) & 0xFF

    rest, micro = divmod(time_utc, 100)
    rest, seconds = divmod(rest, 100)
    hours, minutes = divmod(rest, 100)
    return f"{year}-{month}-{day} {hours}:{minutes}:{seconds}.{micro}"

def get_datetime_third_decimal_place(df: pd.DataFrame) -> pd.DataFrame:
    if not df.empty:
        df[LABEL_DATETIME] = df[LABEL_DATETIME].apply(
            lambda x: x.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        )

    return df


def get_filtered_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    if LABEL_POS_MODE in df.columns:
        df.loc[df[LABEL_POS_MODE] == "N", LABEL_SPEED] = 0

    start_dt = df.loc[0, LABEL_DATETIME]

    return df[
        (df[LABEL_DATETIME] >= start_dt) & (df[LABEL_DATETIME] <= (start_dt + timedelta(hours=5)))
    ].reset_index(drop=True)
