import struct
from typing import NamedTuple, Tuple

from ohcoach_cell_tools.constants import END_EXPORT_COLUMNS


class EndMessage(NamedTuple):
    power_off: bytes
    battery_voltage: int
    operation_time: int
    used_nand_block_size: int
    used_nand_page_size: int

    end_message_struct = struct.Struct("<cHHHH")
    message_length = end_message_struct.size

    @classmethod
    def create(cls, payload):
        return cls._make(cls.end_message_struct.unpack(payload))

    @property
    def power_off_indication(self) -> str:
        return self.power_off.decode("utf-8")

    def export_row(self) -> Tuple:
        return tuple(getattr(self, column) for column in END_EXPORT_COLUMNS)
