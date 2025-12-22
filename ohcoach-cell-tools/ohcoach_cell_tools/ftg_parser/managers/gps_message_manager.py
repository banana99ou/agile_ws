import pandas as pd
import datetime

from ohcoach_cell_tools.ftg_parser.managers.ftg_message_manager import MessageManager
from ohcoach_cell_tools.ftg_parser.messages.gps_message import GpsMessage


class GpsMessageManager(MessageManager):
    def __init__(self):
        super().__init__(GpsMessage)
        self.first_valid_datetime = datetime.datetime(1900,1,1,0,0,0)
        self.messages = []

    def clear(self):
        self.messages.clear()

    def add_message(self, payload: bytes) -> None:
        self.messages.append(payload)
   
    def fix_invalid_datetime(self, df: pd.DataFrame) -> pd.DataFrame:
        df.reset_index(drop=True, inplace=True)
        period = datetime.timedelta(milliseconds=100)
        try:
            idx = df[df["pos_mode"] != "N"].index[0]
        except IndexError:
            return df
        else:
            curr_datetime = df.loc[idx, "datetime"]
            self.first_valid_datetime = curr_datetime
            for i in range(idx-1, -1, -1):
                curr_datetime -= period
                df.loc[i, "datetime"] = curr_datetime
            return df

    def export_dataframe(self) -> pd.DataFrame:
        gps_message_dataframe = GpsMessage.get_calculated_dataframe(self.messages)
        gps_message_dataframe = self.fix_invalid_datetime(gps_message_dataframe)

        if not gps_message_dataframe.empty:
            self.clear()

        return gps_message_dataframe
