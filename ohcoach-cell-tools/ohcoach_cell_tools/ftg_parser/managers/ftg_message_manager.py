import abc
from datetime import datetime, timedelta

import pandas as pd

from ohcoach_cell_tools.constants import LABEL_DATETIME


class MessageManager(abc.ABC):
    def __init__(self, message_class):
        self.message_class = message_class

    @abc.abstractmethod
    def add_message(self, payload: bytes) -> None:
        pass

    @abc.abstractmethod
    def export_dataframe(self) -> pd.DataFrame:
        pass

    @abc.abstractmethod
    def clear(self) -> None:
        pass

    @property
    def message_length(self) -> int:
        return self.message_class.message_length

    @staticmethod
    def adjust_date(dataframe: pd.DataFrame, date: datetime) -> pd.DataFrame:
        date_delta: timedelta = date.date() - dataframe.at[0, LABEL_DATETIME].date()
        dataframe[[LABEL_DATETIME]] += date_delta

        day_change = dataframe[LABEL_DATETIME].diff() < pd.Timedelta(0)
        dataframe[LABEL_DATETIME] += pd.to_timedelta(day_change.cumsum(), unit="d")

        return dataframe

    @staticmethod
    def drop_reversed_datetime_rows(dataframe: pd.DataFrame) -> None:
        if dataframe.empty:
            return

        dataframe["time_reversed"] = dataframe[LABEL_DATETIME].diff() < pd.Timedelta(0)

        time_revesed_rows = dataframe[dataframe["time_reversed"]]
        end_cursor = dataframe.iloc[-1].name

        for i in range(len(time_revesed_rows)):
            row_number = time_revesed_rows.iloc[i].name

            if row_number == 0:
                dataframe.at[row_number, "time_reversed"] = False
                continue

            prev_datetime = dataframe.at[row_number - 1, LABEL_DATETIME]
            next_datetime = dataframe.at[row_number, LABEL_DATETIME]

            if prev_datetime.hour == 23 and next_datetime.hour == 0:
                dataframe.at[row_number, "time_reversed"] = False
                continue

            row_cursor = row_number

            while next_datetime - prev_datetime <= pd.Timedelta(0):
                dataframe.at[row_cursor, "time_reversed"] = True
                if row_cursor == end_cursor:
                    break
                row_cursor += 1
                next_datetime = dataframe.at[row_cursor, LABEL_DATETIME]

        dataframe.drop(
            dataframe[dataframe["time_reversed"]].index,
            inplace=True,
        )

        dataframe.drop(labels=["time_reversed"], axis=1, inplace=True)
