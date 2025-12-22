from typing import Optional

import pandas as pd

from ohcoach_cell_tools.ftg_parser.managers.ftg_message_manager import MessageManager
from ohcoach_cell_tools.ftg_parser.messages.end_message import EndMessage


class EndMessageManager(MessageManager):
    def __init__(self):
        super().__init__(EndMessage)

        self.messages = None

    def clear(self):
        self.messages = None

    def add_message(self, payload: bytes) -> None:
        self.messages = EndMessage.create(payload)

    @property
    def message(self) -> Optional[EndMessage]:
        return self.messages

    def export_dataframe(self) -> pd.DataFrame:
        pass
