from typing import Optional

import pandas as pd

from ohcoach_cell_tools.ftg_parser.managers.ftg_message_manager import MessageManager
from ohcoach_cell_tools.ftg_parser.messages.start_message import StartMessage


class StartMessageManager(MessageManager):
    def __init__(self):
        super().__init__(StartMessage)

        self.messages = None

    def clear(self):
        self.messages = None

    def add_message(self, payload: bytes) -> None:
        self.messages = StartMessage.create(payload)

    @property
    def message(self) -> Optional[StartMessage]:
        return self.messages

    def export_dataframe(self) -> pd.DataFrame:
        pass
