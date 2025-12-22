import pytest

from ohcoach_cell_tools.ftg_parser.managers.start_message_manager import StartMessageManager
from ohcoach_cell_tools.ftg_parser.messages.start_message import StartMessage

raw_start_messages = b"\xae\xb2LCXBC4\x05\x06226-\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00@\x01\xbe\x00\xa0\x1a\xbe\x00\x00I\xbeLsG\xc1\x91\x92\xe7\xbf\xc9\xb3\x8c\xbd\x00\x80\x97?\x00\x80\x97?\x00\x00\x92?"


expected_added_messages = StartMessage(
    cell_serial_number=45742,
    product_id=b"LC",
    version_id=b"XB",
    product_version=b"C4",
    firmware_major_version=5,
    firmware_minor_version=6,
    esp32_firmware_version_bytes=b"226",
    gnss_fix_time=45,
    used_nand_block_size=0,
    used_nand_page_size=0,
    ble_id=b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
    imu_cal_accx=-0.126220703125,
    imu_cal_accy=-0.1510009765625,
    imu_cal_accz=-0.1962890625,
    imu_cal_gyrx=-12.465648651123047,
    imu_cal_gyry=-1.8091603517532349,
    imu_cal_gyrz=-0.06870228797197342,
    imu_cal_magx=1.18359375,
    imu_cal_magy=1.18359375,
    imu_cal_magz=1.140625,
)


@pytest.fixture
def start_message_manager():
    message_manager = StartMessageManager()

    message_manager.add_message(raw_start_messages)

    yield message_manager


class TestStartMessageManager:
    def test_add_message(self):
        # Given: StartMessageManager instance and raw start messages
        start_message_manager = StartMessageManager()

        # When: StartMessageManager.add_message is called on raw start messages
        start_message_manager.add_message(raw_start_messages)

        # Then: list of added messages should eqaul as expected str
        assert start_message_manager.messages == expected_added_messages

    def test_message_not_empty(self, start_message_manager):
        # Given: StartMessageManager.messages not empty

        # When: StartMessageManager.message is called
        start_message = start_message_manager.message

        # Then: start_message should be equal expected
        assert start_message == expected_added_messages

    def test_message_empty(self, start_message_manager):
        # Given: StartMessageManager.messages empty
        start_message_manager = StartMessageManager()

        # When: StartMessageManager.message is called
        start_message = start_message_manager.message

        # Then: start_message should be equal expected
        assert start_message is None

    def test_clear(self, start_message_manager):
        # When: call clear method
        start_message_manager.clear()

        # Then: messages list should be empty
        assert start_message_manager.messages is None
