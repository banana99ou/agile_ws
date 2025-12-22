import pytest

from ohcoach_cell_tools.gp_im_parser.utils.cell_info_utils import CellInfo


class TestCellInfo:
    @pytest.mark.parametrize(
        "file_path, expected_device_model, expected_device_version, expected_device_number, expected_firmware_version",
        [
            ("CLBX-4B-41561_2.0_0_1641270807_0.gp", "CLBX", "4B", 41561, "2.0"),
            ("CLBX-4B-41561_2.0_0_1641270807_0.im", "CLBX", "4B", 41561, "2.0"),
            ("CLBX-3A-33490_3.3_0_1658801686_1.gp", "CLBX", "3A", 33490, "3.3"),
            ("CLBX-3A-33490_3.3_0_1658801686_1.im", "CLBX", "3A", 33490, "3.3"),
            ("CLBX-3A-50417_4.3_17610_1659281001_0.gp", "CLBX", "3A", 50417, "4.3"),
            ("CLBX-3A-50334_4.3_17610_1659287981_0.im", "CLBX", "3A", 50334, "4.3"),
        ],
    )
    def test_cell_info_parsed(
        self,
        file_path,
        expected_device_model,
        expected_device_version,
        expected_device_number,
        expected_firmware_version,
    ):
        # When: call CellInfo
        cell_info = CellInfo(file_path=file_path)

        # Then: device_model should be euqal expected_device_model
        assert cell_info.device_model == expected_device_model
        # AND: device_version should be euqal expected_device_version
        assert cell_info.device_version == expected_device_version
        # AND: device_number should be euqal expected_device_number
        assert cell_info.device_number == expected_device_number
        # AND: firmware_version should be euqal expected_firmware_version
        assert cell_info.firmware_version == expected_firmware_version
