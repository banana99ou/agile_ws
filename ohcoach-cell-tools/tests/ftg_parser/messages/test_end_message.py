from ohcoach_cell_tools.ftg_parser.messages.end_message import EndMessage

end_message_bytes = b"N\xaa\x01\xbf\x01\r\x006\x00"

expected_end_message = EndMessage(
    power_off=b"N",
    battery_voltage=426,
    operation_time=447,
    used_nand_block_size=13,
    used_nand_page_size=54,
)


class TestEndMessage:
    def test_message_length(self):
        assert EndMessage.message_length == 9

    def test_bytes_message_parsed_correctly(self):
        # When: EndMessage.create is called on raw end message
        actual_end_message = EndMessage.create(end_message_bytes)

        # Then: parsed message should eqaul to expected
        assert actual_end_message == expected_end_message

    def test_power_off_indication(self):
        expected_power_off_indication = "N"

        # Given: parsed and created EndMessage from raw bytes of message
        end_message = EndMessage.create(end_message_bytes)

        # When: call power_off_indication property
        actual_power_off_indication = end_message.power_off_indication

        # Then: power_off_indication matches
        assert actual_power_off_indication == expected_power_off_indication
