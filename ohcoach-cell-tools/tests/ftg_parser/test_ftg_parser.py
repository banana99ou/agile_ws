from datetime import datetime
from unittest import mock

import pytest

from ohcoach_cell_tools.constants import BS_EXPORT_COLUMNS, GPS_EXPORT_COLUMNS, IMU_EXPORT_COLUMNS
from ohcoach_cell_tools.ftg_parser.ftg_parser import (
    BS_MSG_TYPE,
    END_MSG_TYPE,
    GPS_MSG_TYPE,
    IMU_MSG_TYPE,
    MSG_PAYLOAD_OFFSET,
    START_MSG_TYPE,
    FtgParser,
)
from ohcoach_cell_tools.ftg_parser.messages.bs_message import BsMessage
from ohcoach_cell_tools.ftg_parser.messages.end_message import EndMessage
from ohcoach_cell_tools.ftg_parser.messages.gps_message import GpsMessage
from ohcoach_cell_tools.ftg_parser.messages.imu_message import ImuMessage
from ohcoach_cell_tools.ftg_parser.messages.start_message import StartMessage

dummy_on_top = b"\xca`\x02\xe0\x01I"
start_message = b"COACH\x04O\xae\x08LCXBA3\x03\x00\x31\x34\x39\x15\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00\xa0\x9c\xbd\x00\x00|<\x00@\xeb\xbd\xee\x82\xbf\xc0/\xf8\xab>/\xf8\xab\xbf\x00\x80\x96?\x00\x80\x97?\x00\x80\x91?\xca\r\n"
gps_messge = b"COACH\x014\xe4\x07\x02\x13j\xdb\t\x01P\xcf\x02\x13W\x00\x00\x00(\xb3\xa7\xdb'\x01\x00\x00\xde\x13\x02\x00|\x15\xec\x13\xd6\x06\x00\x00Pr\x00\x00\x00\x00\xd1\x00\xda\x00\xaf\x00\x06\x06)A\x01\r\n"
imu_message = (
    b"COACH\x02\x16j\xdb\t\x01\xff1\x00(\xf7\x1c\xff\x95\x00\x03\xff\xf7P\x01\xfc\x00\xa4\xfe6\r\n"
)
bs_message = b"COACH\x03\x18\xe4\x07\x02\x13t\xdb\t\x01\x01\x00\x00\x00\x00\x00[\x01\xfe\xfe\x00\x00\x00\x00\x00\x00\x15\r\n"
end_message = b"COACH\x05\tNX\x017\x00\x02\x00&\x00\x08\r\n\xff@@DUMMY@DUMMY@DUMMY@@@@@@@DUMMY@DUMMY@DUMMY@DUMMY@DUMMY@@"

raw_bytes = dummy_on_top + start_message + gps_messge + imu_message + bs_message + end_message

raw_data_including_wrong_message = (
    b"COACH\x02PWROF\xfa\xe9\xfe5\xfb\x97\x01e\x00\xb4\x00\\-\x00U\x025\xff\x90\r\n"
    b"COACH\x05\tN\x8f\x01\x15\x01\t\x00\n\x00\xdb\r\nn@@GPSEND"
)

gps_message_payload = b"\xe4\x07\x02\x13j\xdb\t\x01P\xcf\x02\x13W\x00\x00\x00(\xb3\xa7\xdb'\x01\x00\x00\xde\x13\x02\x00|\x15\xec\x13\xd6\x06\x00\x00Pr\x00\x00\x00\x00\xd1\x00\xda\x00\xaf\x00\x06\x06)A"
expected_gps_message_messages = [
    b"\xe4\x07\x02\x13j\xdb\t\x01P\xcf\x02\x13W\x00\x00\x00(\xb3\xa7\xdb'\x01\x00\x00\xde\x13\x02\x00|\x15\xec\x13\xd6\x06\x00\x00Pr\x00\x00\x00\x00\xd1\x00\xda\x00\xaf\x00\x06\x06)A"
]

yield_payload_data = (
    b"\xceVLCXBA3\x03\x00149>\x00\xff\xff\xff\xffPolar OH1 8714ED23\x00\x00\x00\x00\x00\x00\x00\x00l\xbd\x00\x00\x00\x00\x00\x00\x02<)y\x96\xc0\x00\x00\x00\x00\xe5Y\xc6\xbf\x00\x00\x9b?\x00\x00\x00\x00\x00\x00\x9c?",
    b"\xe4\x07\x02\x13j\xdb\t\x01P\xcf\x02\x13W\x00\x00\x00(\xb3\xa7\xdb'\x01\x00\x00\xde\x13\x02\x00|\x15\xec\x13\xd6\x06\x00\x00Pr\x00\x00\x00\x00\xd1\x00\xda\x00\xaf\x00\x06\x06)A",
    b"j\xdb\t\x01\xff1\x00(\xf7\x1c\xff\x95\x00\x03\xff\xf7P\x01\xfc\x00\xa4\xfe",
    b"\xe4\x07\x02\x13t\xdb\t\x01\x01\x00\x00\x00\x00\x00[\x01\xfe\xfe\x00\x00\x00\x00\x00\x00",
    b"NX\x017\x00\x02\x00&\x00",
)


class TestFtgParser:
    @staticmethod
    def _auxiliary_crc_calculator(data):
        crc = 0

        for each_byte in data:
            crc ^= each_byte

        return crc

    def test_crc_check_on_dummy(self):
        # Given: CRC value comes at last
        dummy_data = b"ABCDEDFGHIJLMNOP"

        expected_crc_value = TestFtgParser._auxiliary_crc_calculator(dummy_data)

        # When: FtgParser._crc_check is called
        actual_test_result = FtgParser._crc_check(dummy_data, expected_crc_value)

        # Then: the test should be passed
        assert actual_test_result is True

        # And when: FtgParser._crc_check is called on wrong crc value
        wrong_crc_value = expected_crc_value - 1
        actual_false_result = FtgParser._crc_check(dummy_data, wrong_crc_value)

        # Then: the test should be failed
        assert actual_false_result is False

    @pytest.mark.parametrize(
        "message_type, message_length",
        [
            (START_MSG_TYPE, StartMessage.message_length),
            (END_MSG_TYPE, EndMessage.message_length),
            (GPS_MSG_TYPE, GpsMessage.message_length),
            (IMU_MSG_TYPE, ImuMessage.message_length),
            (BS_MSG_TYPE, BsMessage.message_length),
        ],
    )
    def test_get_defined_msg_length(self, message_type, message_length):
        # defined message length of message_type should equals to message_length
        assert FtgParser._get_defined_msg_length(message_type) == message_length

    def test_find_next_message(self):
        # Given: .ftg file buffer: memory view
        memview = memoryview(raw_bytes)

        # When: FtgParser.find_next_message is called on memoryview: from the first
        new_cursor, message = FtgParser.find_next_message(memview, 0)

        # Then: message should not be None and tests should be passed
        assert message is not None

        msg_type, crc_data, payload, crc = message

        assert new_cursor > len(payload)
        assert msg_type == START_MSG_TYPE
        assert FtgParser._crc_check(crc_data, crc) is True
        assert StartMessage.start_message_struct.size == len(payload)

    def test_find_next_message_should_skip_wrong_recorded_message(self):
        # Given: .ftg file buffer: memory view: the first message is wrong
        memview = memoryview(raw_data_including_wrong_message)

        # When: FtgParser.find_next_message is called
        initial_cursor = 0
        new_cursor, message = FtgParser.find_next_message(memview, initial_cursor)

        # Then: the wrong message should be skipped and error message be appended
        expected_error_message = "[FTG-Parser] FNM: Length Error type: 2 / length: 80"

        assert message == expected_error_message
        assert new_cursor == initial_cursor + MSG_PAYLOAD_OFFSET

    def test_parse(self):
        # When: file buffer with 5 types of messages are passed to parse method
        parse_generator = FtgParser.parse(raw_bytes)

        # Then: the generator should yield a 5-tuple of start msg, 3 dataframes, and end msg
        result = next(parse_generator)

        assert len(result) == 6
        assert result[0] is not None
        assert result[1].size == len(GPS_EXPORT_COLUMNS)
        assert result[2].size == len(IMU_EXPORT_COLUMNS)
        assert result[3].size == len(BS_EXPORT_COLUMNS)

    def test_raw_parser(self):
        # Given: .ftg file buffer: memory view
        memview = memoryview(raw_bytes)

        # When: raw_parser is called and all of its contents are consumed
        result = tuple(FtgParser.raw_parser(memview))

        # Then: all messages with b'COACH' prefix should be parsed: length should be 5
        assert len(result) == 5

    def test_raw_parser_should_skip_wrong_recorded_message(self):
        # Given: .ftg file buffer which contains a wrong message
        memview = memoryview(raw_data_including_wrong_message)

        # When: raw_parser is called
        result = tuple(FtgParser.raw_parser(memview))

        # Then: only valid message should be parsed (only one in this case)
        assert len(result) == 1

        assert len(FtgParser.parsing_errors) == 1

        FtgParser.parsing_errors.clear()

    def test_prepare_dataframes_to_yield_when_all_managers_empty(self):
        # Given: make sure that every manager's messages are empty
        FtgParser.gps_message_manager.messages = []
        FtgParser.imu_message_manager.messages = []
        FtgParser.bs_message_manager.messages = []

        # When: call prepare_dataframes_to_yield to retrieve dataframes
        gps_df, imu_df, bs_df = FtgParser.prepare_dataframes_to_yield()

        # Then: all datafrmes are empty
        assert gps_df.empty is True
        assert imu_df.empty is True
        assert bs_df.empty is True

    def test_prepare_dataframes_to_yield(self):
        gps_row = b"\xe7\x07\x02\x02,\xc3\x06\x00x\xfd\x83\xf5Q\x00\x00\x00p\x0f %D\x01\x00\x00\xfa\xbd\x00\x00\xa0\x0f$\x13N\x00\x00\x00\x00\x00\xf9\xff\xff\xff\x8a\x00\xa2\x00q\x00\x06\x0f'A"
        imu_row = b",\xc3\x06\x00\xffI\x00:\xf7]\xff\x9e\x00.\xff\xfbQ\x00\xb9\xff\x17\xff"
        bs_row = b"\xe7\x07\x02\x02@\xc3\x06\x00\x01\x00\x00\x00\x00\x00\xa2\x01\x00\x00\x01\x00\x00\x00\x00\x00"

        # Given: each managers has a exported record
        FtgParser.gps_message_manager.messages.append(gps_row)
        FtgParser.imu_message_manager.messages.append(imu_row)
        FtgParser.bs_message_manager.messages.append(bs_row)

        # When: call prepare_dataframes_to_yield to retrieve dataframes
        gps_df, imu_df, bs_df = FtgParser.prepare_dataframes_to_yield()

        # Then: each dataframes has one row
        assert len(gps_df) == 1
        assert len(imu_df) == 1
        assert len(bs_df) == 1

        # And: imu's datetime has adjusted
        assert imu_df.at[0, "datetime"] == datetime(2023, 2, 2, 0, 44, 31, 800000)

    def test_check_managers_not_empty(self):
        # Given: GpsMessageManager or ImuMessageManager or BsMessageManager has a messages
        FtgParser.gps_message_manager.add_message(gps_message_payload)

        # When: FtgParser.check_managers_not_empty is called
        result = FtgParser.check_managers_not_empty()

        # Then: result should be equal True
        assert result is True

        FtgParser.gps_message_manager.clear()

    def test_add_payload_to_message_list(self):
        # Given: message_type and payload
        message_type = GPS_MSG_TYPE
        payload = gps_message_payload

        # When: FtgParser.add_payload_to_message_list is called
        FtgParser.add_payload_to_message_list(message_type, payload)

        # Then: messages for that class must contain data
        result = FtgParser.gps_message_manager.messages
        assert result == expected_gps_message_messages

        FtgParser.gps_message_manager.clear()

    def test_add_payload_to_message_list_error(self):
        expected = ["[FTG-Parser] ERROR: message type: 0 / exception: 0"]
        # Given: wrond message_type and payload
        message_type = 0x00
        payload = gps_message_payload

        # When: FtgParser.add_payload_to_message_list is called
        FtgParser.add_payload_to_message_list(message_type, payload)

        # Then: parsing_error_message contain error_message
        result = FtgParser.parsing_errors
        assert result == expected

        FtgParser.gps_message_manager.clear()
        FtgParser.parsing_errors.clear()

    @mock.patch.object(FtgParser, "prepare_dataframes_to_yield", side_effect=Exception())
    def test_clear(self, _):
        # When: emulate FtaParser which raises Exception while parsing
        try:
            parse_generator = FtgParser.parse(raw_bytes)
            next(parse_generator)
        except Exception:
            pass

        # Then: all intermediate parsing result should be cleared
        assert len(FtgParser.gps_message_manager.messages) == 0
        assert len(FtgParser.imu_message_manager.messages) == 0
        assert len(FtgParser.bs_message_manager.messages) == 0
        assert len(FtgParser.parsing_errors) == 0

    def test_end_message_not_found(self):
        # Given: raw buffer with no end message
        raw_bytes_without_end = start_message + gps_messge + imu_message + bs_message

        parse_generator = FtgParser.parse(raw_bytes_without_end)

        (start, rgp, rim, rbs, end, errors) = next(parse_generator)

        assert start is not None
        assert len(rgp) == 1
        assert len(rim) == 1
        assert len(rbs) == 1
        assert end is None
        assert errors == ["[FTG-Parser] ERROR: End message not found"]

        FtgParser.parsing_errors.clear()
