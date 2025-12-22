from typing import Any, Generator, Tuple, Union
import re  # 추가

import pandas as pd
import sys
import re

from ohcoach_cell_tools.ftg_parser.managers.bs_message_manager import BsMessageManager
from ohcoach_cell_tools.ftg_parser.managers.end_message_manager import EndMessageManager
from ohcoach_cell_tools.ftg_parser.managers.ftg_message_manager import MessageManager
from ohcoach_cell_tools.ftg_parser.managers.gps_message_manager import GpsMessageManager
from ohcoach_cell_tools.ftg_parser.managers.imu_message_manager import (
    ImuMessageManager, Imu0x0EMessageManager, Imu0x0FMessageManager
)
from ohcoach_cell_tools.ftg_parser.managers.start_message_manager import StartMessageManager
from ohcoach_cell_tools.ftg_parser.messages.bs_message import BsMessage
from ohcoach_cell_tools.ftg_parser.messages.end_message import EndMessage
from ohcoach_cell_tools.ftg_parser.messages.gps_message import GpsMessage
from ohcoach_cell_tools.ftg_parser.messages.imu_message import (
    ImuMessage, Imu0x0EMessage, Imu0x0FMessage
)
from ohcoach_cell_tools.ftg_parser.messages.start_message import StartMessage

PARSED_MESSAGE = Tuple[int, memoryview, memoryview, int]

HEADER_DELIMITER = b"COACH"
FITO_LOG_START_DELIMITER_PATTERN = re.compile(br"\(\d{8}\)")
GPS_MSG_TYPE = 0x01
IMU_MSG_TYPE = 0x02
BS_MSG_TYPE = 0x03
START_MSG_TYPE = 0x04
END_MSG_TYPE = 0x05
IMU_0x0E_MSG_TYPE = 0x0E
IMU_0x0F_MSG_TYPE = 0x0F

MSG_TYPE_OFFSET = len(HEADER_DELIMITER)
MSG_LENGTH_OFFSET = MSG_TYPE_OFFSET + 1
MSG_PAYLOAD_OFFSET = MSG_LENGTH_OFFSET + 1

PARSE_LENGTH_ERROR = "[FTG-Parser] FNM: Length Error type: {} / length: {}"


class FtgParser:
    gps_message_manager = GpsMessageManager()
    imu_message_manager = ImuMessageManager()
    imu_0x0E_message_manager = Imu0x0EMessageManager()
    imu_0x0F_message_manager = Imu0x0FMessageManager()
    bs_message_manager = BsMessageManager()
    start_message_manager = StartMessageManager()
    end_message_manager = EndMessageManager()

    managers = {
        GPS_MSG_TYPE: gps_message_manager,
        IMU_MSG_TYPE: imu_message_manager,
        BS_MSG_TYPE: bs_message_manager,
        START_MSG_TYPE: start_message_manager,
        END_MSG_TYPE: end_message_manager,
        IMU_0x0E_MSG_TYPE: imu_0x0E_message_manager,
        IMU_0x0F_MSG_TYPE: imu_0x0F_message_manager,    }

    parsing_errors: list[str] = []

    @classmethod
    def clear(cls):
        cls.gps_message_manager.clear()
        cls.imu_message_manager.clear()
        cls.bs_message_manager.clear()
        cls.imu_0x0E_message_manager.clear()
        cls.imu_0x0F_message_manager.clear()
        cls.clear_parse_start_end_message_after_data_yield()

    @classmethod
    def clear_parse_start_end_message_after_data_yield(cls):
        cls.start_message_manager.clear()
        cls.end_message_manager.clear()
        cls.parsing_errors.clear()

    @staticmethod
    def _crc_check(data_to_check, crc_value) -> bool:
        crc = 0

        for each_byte in data_to_check:
            crc ^= each_byte

        return crc == crc_value

    @classmethod
    def _get_defined_msg_length(cls, msg_type) -> int:
        if msg_type == IMU_MSG_TYPE:
            return ImuMessage.message_length
        elif msg_type == GPS_MSG_TYPE:
            return GpsMessage.message_length
        elif msg_type == BS_MSG_TYPE:
            return BsMessage.message_length
        elif msg_type == START_MSG_TYPE:
            return StartMessage.message_length
        elif msg_type == END_MSG_TYPE:
            return EndMessage.message_length
        elif msg_type == IMU_0x0E_MSG_TYPE:
            return Imu0x0EMessage.message_length
        elif msg_type == IMU_0x0F_MSG_TYPE:
            return Imu0x0FMessage.message_length

        return 0

    @classmethod
    def find_next_message(
        cls, buffer: memoryview, cursor: int
    ) -> Tuple[int, Union[str, PARSED_MESSAGE]]:
        msg_first_index = buffer.obj.index(HEADER_DELIMITER, cursor)

        msg_type_index = msg_first_index + MSG_TYPE_OFFSET
        msg_length_index = msg_first_index + MSG_LENGTH_OFFSET
        msg_payload_index = msg_first_index + MSG_PAYLOAD_OFFSET

        msg_length = buffer[msg_length_index]
        msg_type = buffer[msg_type_index]

        defined_msg_length = cls._get_defined_msg_length(msg_type)

        if defined_msg_length != msg_length:
            return msg_payload_index, PARSE_LENGTH_ERROR.format(msg_type, msg_length)

        msg_crc_index = msg_payload_index + msg_length

        crc_data = buffer[msg_type_index:msg_crc_index]
        payload = buffer[msg_payload_index:msg_crc_index]
        crc = buffer[msg_crc_index]

        return msg_crc_index, (msg_type, crc_data, payload, crc)

    @staticmethod
    def is_message_parsed_correctly(obj: Any) -> bool:
        return True if type(obj) is tuple else False

    @classmethod
    def raw_parser(cls, file_contents: memoryview) -> Generator[PARSED_MESSAGE, None, None]:
        cursor = 0
        try:
            match = FITO_LOG_START_DELIMITER_PATTERN.search(file_contents)
            max_cursor = match.start() if match else sys.maxsize
        except Exception:
            print("[FTG-Parser] ERROR: No start delimiter found")
            max_cursor = sys.maxsize

        while True:
            try:
                cursor, message = FtgParser.find_next_message(file_contents, cursor)

                if cursor >= max_cursor:
                    break
                elif type(message) is tuple:
                    yield message
                else:
                    raise Exception(message)
            except ValueError:
                break
            except Exception as e:
                cls.parsing_errors.append(str(e))
                cursor += MSG_TYPE_OFFSET

    @classmethod
    def prepare_dataframes_to_yield(cls) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        gps_dataframe = cls.gps_message_manager.export_dataframe()

        imu_dataframe =  None
        if not cls.imu_message_manager.messages:
            imu_0x0E_dataframe = cls.imu_0x0E_message_manager.export_dataframe()
            imu_0x0F_dataframe = cls.imu_0x0F_message_manager.export_dataframe()

            imu_dataframe = pd.concat([imu_0x0E_dataframe, imu_0x0F_dataframe]).sort_values(
                by=["datetime"], ascending=True
            )
            imu_dataframe = imu_dataframe.set_index("datetime")
            imu_dataframe = imu_dataframe.reset_index()
        else:
            imu_dataframe = cls.imu_message_manager.export_dataframe()

        first_valid_datetime = cls.gps_message_manager.first_valid_datetime
        bs_dataframe = cls.bs_message_manager.export_dataframe(first_valid_datetime)

        # MessageManager.drop_reversed_datetime_rows(gps_dataframe)
        # MessageManager.drop_reversed_datetime_rows(imu_dataframe)
        # MessageManager.drop_reversed_datetime_rows(bs_dataframe)

        if not (gps_dataframe.empty or imu_dataframe.empty):
            first_datetime = gps_dataframe.at[0, "datetime"]

            imu_dataframe = MessageManager.adjust_date(
                imu_dataframe,
                first_datetime,
            )

        return (
            gps_dataframe,
            imu_dataframe,
            bs_dataframe,
        )

    @classmethod
    def check_managers_not_empty(cls) -> bool:
        for manager in cls.managers.values():
            if (
                manager.message_class in (GpsMessage, ImuMessage, BsMessage)
                and len(manager.messages) != 0
            ):
                return True
        return False

    @classmethod
    def add_payload_to_message_list(cls, message_type: int, payload: bytes) -> None:
        try:
            cls.managers[message_type].add_message(payload)
        except Exception as e:
            cls.parsing_errors.append(
                f"[FTG-Parser] ERROR: message type: { message_type } / exception: { e }"
            )

    @classmethod
    def parse(cls, file_contents) -> Generator:
        try:
            mv_contents = memoryview(file_contents)

            for (message_type, crc_data, payload, crc) in FtgParser.raw_parser(mv_contents):
                if FtgParser._crc_check(crc_data, crc):
                    if message_type == START_MSG_TYPE:
                        if cls.check_managers_not_empty():
                            yield (
                                cls.start_message_manager.message,
                                *cls.prepare_dataframes_to_yield(),
                                cls.end_message_manager.message,
                                cls.parsing_errors,
                            )
                            cls.clear_parse_start_end_message_after_data_yield()

                    cls.add_payload_to_message_list(message_type, payload)

                    if message_type == END_MSG_TYPE:
                        yield (
                            cls.start_message_manager.message,
                            *cls.prepare_dataframes_to_yield(),
                            cls.end_message_manager.message,
                            cls.parsing_errors,
                        )
                        cls.clear_parse_start_end_message_after_data_yield()
                else:
                    cls.parsing_errors.append(
                        f"[FTG-Parser] ERROR: CRC error msg_type: {message_type} / crc: {crc}"
                    )

            if cls.check_managers_not_empty():
                cls.parsing_errors.append("[FTG-Parser] ERROR: End message not found")
                yield (
                    cls.start_message_manager.message,
                    *cls.prepare_dataframes_to_yield(),
                    cls.end_message_manager.message,
                    cls.parsing_errors,
                )

        except Exception as e:
            raise e
        finally:
            cls.clear()
