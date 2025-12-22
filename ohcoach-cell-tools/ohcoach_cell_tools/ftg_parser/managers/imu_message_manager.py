import pandas as pd

from ohcoach_cell_tools.ftg_parser.managers.ftg_message_manager import MessageManager
from ohcoach_cell_tools.ftg_parser.messages.imu_message import (ImuMessage, Imu0x0EMessage,
                                                                 Imu0x0FMessage)


class ImuMessageManager(MessageManager):
    def __init__(self):
        super().__init__(ImuMessage)

        self.messages = []

    def clear(self):
        self.messages.clear()

    def add_message(self, payload: bytes) -> None:
        self.messages.append(payload)
        # self.messages.append(ImuMessage.convert_payload(bytearray(payload)))

    def export_dataframe(self) -> pd.DataFrame:
        df = ImuMessage.get_calculated_dataframe(self.messages)
        if df.empty:
            return df
        else:
            self.clear()
            return df


class Imu0x0EMessageManager(MessageManager):
    def __init__(self):
        super().__init__(Imu0x0EMessage)

        self.messages = []

    def clear(self):
        self.messages.clear()
        super().clear()

    def add_message(self, payload: bytes) -> None:
        self.messages.append(payload)
    
    def export_dataframe(self) -> pd.DataFrame:
        df = Imu0x0EMessage.get_calculated_dataframe(self.messages)
        if df.empty:
            return df
        else:
            self.clear()
            return df


class Imu0x0FMessageManager(MessageManager):
    def __init__(self):
        super().__init__(Imu0x0FMessage)

        self.messages = []

    def clear(self):
        self.messages.clear()
        super().clear()

    def add_message(self, payload: bytes) -> None:
        self.messages.append(payload)
    
    def export_dataframe(self) -> pd.DataFrame:
        df = Imu0x0FMessage.get_calculated_dataframe(self.messages)
        if df.empty:
            return df
        else:
            self.clear()
            return df

