import pytest

from ohcoach_cell_tools.ftg_parser.managers.end_message_manager import EndMessageManager
from ohcoach_cell_tools.ftg_parser.messages.end_message import EndMessage

raw_end_messages = b"N\xc4\x01>\x00\x02\x004\x00"

expected_added_messages = EndMessage(
    power_off=b"N",
    battery_voltage=452,
    operation_time=62,
    used_nand_block_size=2,
    used_nand_page_size=52,
)


@pytest.fixture
def end_message_manager():
    message_manager = EndMessageManager()

    message_manager.add_message(raw_end_messages)

    yield message_manager


class TestEndMessageManager:
    def test_add_message(self):
        # Given: EndMessageManager instance and raw end messages
        end_message_manager = EndMessageManager()

        # When: EndMessageManager.add_message is called on raw end messages
        end_message_manager.add_message(raw_end_messages)

        # Then: list of added messages should eqaul as expected str
        assert end_message_manager.messages == expected_added_messages

    def test_message_not_empty(self, end_message_manager):
        # Given: EndMessageManager.messages not empty

        # When: EndMessageManager.message is called
        end_message = end_message_manager.message

        # Then: end_message should be equal expected
        assert end_message == expected_added_messages

    def test_message_empty(self, end_message_manager):
        # Given: EndMessageManager.messages empty
        end_message_manager = EndMessageManager()

        # When: EndMessageManager.message is called
        end_message = end_message_manager.message

        # Then: end_message should be equal expected
        assert end_message is None

    def test_clear(self, end_message_manager):
        # When: call clear method
        end_message_manager.clear()

        # Then: messages list should be empty
        assert end_message_manager.messages is None
