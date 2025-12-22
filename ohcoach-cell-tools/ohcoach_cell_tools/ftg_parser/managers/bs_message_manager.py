import pandas as pd
import datetime

from ohcoach_cell_tools.ftg_parser.managers.ftg_message_manager import MessageManager
from ohcoach_cell_tools.ftg_parser.messages.bs_message import BsMessage

CELL_STATE = "cell_state"
CELL_STATE_BLE_CONNECTED = (5, 6, 7, 8)


class BsMessageManager(MessageManager):
    def __init__(self):
        super().__init__(BsMessage)

        self.messages = []

    @staticmethod
    def check_ble_connected(bs_message_dataframe: pd.DataFrame) -> bool:
        if bs_message_dataframe.empty:
            return False

        return any(bs_message_dataframe[CELL_STATE].isin(CELL_STATE_BLE_CONNECTED))

    def clear(self):
        self.messages.clear()

    def add_message(self, payload: bytes) -> None:
        self.messages.append(payload)

    def fix_invalid_datetime(self, df: pd.DataFrame, time_stamp: datetime.datetime) -> pd.DataFrame:
        df.reset_index(drop=True, inplace=True)
        period = datetime.timedelta(seconds=1)
        time_stamp -= datetime.timedelta(microseconds=time_stamp.microsecond)
        time_stamp += datetime.timedelta(seconds=1)
        try:
            idx = df[df["datetime"] == time_stamp].index[0]
        except IndexError:
            return df
        else:
            for i in range(idx-1, -1, -1):
                time_stamp -= period
                df.loc[i, "datetime"] = time_stamp
            return df

    def export_dataframe(self, time_stamp: datetime.datetime) -> pd.DataFrame:
        bs_message_dataframe = BsMessage.get_calculated_dataframe(self.messages)
        bs_message_dataframe = self.fix_invalid_datetime(bs_message_dataframe, time_stamp)
        if not bs_message_dataframe.empty:
            self.clear()

        return bs_message_dataframe
