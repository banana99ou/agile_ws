import pytest

from ohcoach_cell_tools.constants import START_EXPORT_COLUMNS
from ohcoach_cell_tools.ftg_parser.messages.start_message import StartMessage

start_message_bytes = b"\xb9\x08LCXBA5\x03\x00\x31\x34\x39\x1b\x00\xff\xff\xff\xffPolar OH1 8714ED23\x00\x00\x00\x00\x00\x00\x00\x00R\xbd\x00\x00d;\x00\x00\xe0\xbc\xc9\xb3\x8c\xc0Xq\xc2\xbf\xfcU\x1c=\x00\x00\x9b?\x00\x00\x9c?\x00\x00\x96?"

expected_start_message = StartMessage(
    cell_serial_number=2233,
    product_id=b"LC",
    version_id=b"XB",
    product_version=b"A5",
    firmware_major_version=3,
    firmware_minor_version=0,
    esp32_firmware_version_bytes=b"149",
    gnss_fix_time=27,
    used_nand_block_size=65535,
    used_nand_page_size=65535,
    ble_id=b"Polar OH1 8714ED23\x00\x00\x00\x00\x00\x00",
    imu_cal_accx=-0.05126953125,
    imu_cal_accy=0.00347900390625,
    imu_cal_accz=-0.02734375,
    imu_cal_gyrx=-4.396946430206299,
    imu_cal_gyry=-1.5190839767456055,
    imu_cal_gyrz=0.038167938590049744,
    imu_cal_magx=1.2109375,
    imu_cal_magy=1.21875,
    imu_cal_magz=1.171875,
)


class TestStartMessage:
    def test_message_length(self):
        assert StartMessage.message_length == 79

    def test_bytes_message_parsed_correctly(self):
        # When: StartMessage.create is called on raw start message
        actual_start_message = StartMessage.create(start_message_bytes)

        # Then: parsed message should eqaul to expected
        assert actual_start_message == expected_start_message

    def test_imu_accel_calibration(self):
        # When: call imu_accel_calibration property
        actual_imu_accel_calibration = expected_start_message.imu_accel_calibration

        # Then: result tuple values matches
        assert actual_imu_accel_calibration == (
            -0.05126953125,
            0.00347900390625,
            -0.02734375,
        )

    def test_imu_gyro_calibration(self):
        # When: call imu_gyro_calibration property
        actual_imu_gyro_calibration = expected_start_message.imu_gyro_calibration

        # Then: result tuple values matches
        assert actual_imu_gyro_calibration == (
            -4.396946430206299,
            -1.5190839767456055,
            0.038167938590049744,
        )

    def test_imu_magnet_calibration(self):
        # When: call imu_magnet_calibration property
        actual_imu_magnet_calibration = expected_start_message.imu_magnet_calibration

        # Then: result tuple values matches
        assert actual_imu_magnet_calibration == (
            1.2109375,
            1.21875,
            1.171875,
        )

    def test_ble_hr_id_valid_bytes(self):
        # When: call ble_hr_id property
        actual_ble_hr_id = expected_start_message.ble_hr_id

        # Then: result ble id matches (stripped)
        assert actual_ble_hr_id == "Polar OH1 8714ED23"

    @pytest.mark.parametrize(
        "wrong_ble_id, expected_ble_id_hr",
        [
            (b"\xff\xff\xff\xff\xff\xff", ""),
            (b"ABCD\xff\x00\xff\xff", "ABCD"),
            (b"ABC\xff\xff\x00\x00", "ABC"),
        ],
    )
    def test_ble_hr_id_with_invalid_bytes(self, wrong_ble_id, expected_ble_id_hr):
        def substitute_ble_id(field_name, wrong_ble_id):
            return (
                wrong_ble_id
                if field_name == "ble_id"
                else getattr(expected_start_message, field_name)
            )

        # Given: start_message with wrong ble_id which has non-decodible bytes
        new_start = StartMessage(
            *(substitute_ble_id(field_name, wrong_ble_id) for field_name in StartMessage._fields)
        )

        # Then: wrong bytes should be stripped off
        assert new_start.ble_hr_id == expected_ble_id_hr

    def test_firmware_version(self):
        # When: call firmware_version property
        actual_firmware_version = expected_start_message.firmware_version

        # Then: result firmware version values matches
        assert actual_firmware_version == "v3.0"

    def test_esp32_firmware_version(self):
        # When: call esp32_firmware_version property
        actual_esp32_firmware_version = expected_start_message.esp32_firmware_version

        # Then: result esp32 firmware version values matches
        assert actual_esp32_firmware_version == "149"

    def test_device_number(self):
        # When: call device_number property
        actual_device_number = expected_start_message.device_number

        # Then: result tuple values matches
        assert actual_device_number == 2233

    def test_device_version(self):
        # When: call device_version property
        actual_device_version = expected_start_message.device_version

        # Then: result device version values matches
        assert actual_device_version == "5A"

    def test_device_model(self):
        # When: call device_model property
        actual_device_model = expected_start_message.device_model

        # Then: result device model values matches
        assert actual_device_model == "CLBX"

    def test_export_row(self):
        start_message = StartMessage.create(start_message_bytes)

        # When: call export_row property
        actual_exported_row = start_message.export_row()

        # Then: length of exported row tuple should be same as the length of EXPORT_COLUMNS
        assert len(actual_exported_row) == len(START_EXPORT_COLUMNS)
