from datetime import timedelta

import pandas as pd

from ohcoach_cell_tools.constants import LABEL_DATETIME


def get_processed_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df[LABEL_DATETIME] = pd.to_datetime(df[LABEL_DATETIME], errors="coerce")
    df = df.dropna()
    df = __truncate_dataframe_datetime_within_five_hours(df=df)
    df = __get_datetime_thrird_decimal_place(df=df)

    return df.set_index(LABEL_DATETIME).sort_index()


def __truncate_dataframe_datetime_within_five_hours(df: pd.DataFrame) -> pd.DataFrame:
    start_dt = df.loc[0, LABEL_DATETIME]

    return df[
        (df[LABEL_DATETIME] >= start_dt) & (df[LABEL_DATETIME] <= (start_dt + timedelta(hours=5)))
    ]


def __get_datetime_thrird_decimal_place(df: pd.DataFrame) -> pd.DataFrame:
    df[LABEL_DATETIME] = df[LABEL_DATETIME].apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])

    return df
