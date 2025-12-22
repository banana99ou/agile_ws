import pandas as pd
import pytest
from imu_parser_sample_data import TEST_IM_STREAM, TEST_IMU_ROW_DATA

from ohcoach_cell_tools.constants import (
    FORMAT_DATETIME_SSFF,
    FORMAT_INITIAL_DATETIME_YYMMDDHHII,
    HEADER_RIM,
)
from ohcoach_cell_tools.gp_im_parser.imu_parser import ImuParser
from ohcoach_cell_tools.gp_im_parser.utils.gp_im_data_utils import ImuData

EXPECTED_IM_DF = pd.DataFrame(TEST_IMU_ROW_DATA, columns=HEADER_RIM)
EXPECTED_INITIAL_DATA_PACKET_LEN = 7
EXPECTED_DATA_PACKET_LEN = 20


class TestImuParser:
    @pytest.fixture(autouse=True)
    def set_up(self):
        # Given: parsed and create ImuData from im_stream
        self.imu_data = ImuData(
            im_stream=TEST_IM_STREAM, device_version="3A", firmware_version="3.0", frequency=100
        )

    def test_get_imu_parser_data(self):
        # When: call ImuParser
        imu_parser = ImuParser(imu_data=self.imu_data)

        # Then: Generate imu_data Parameters
        assert imu_parser.imu_data == self.imu_data
        # AND: Generate format_initial_datetime Parameters
        assert imu_parser.format_initial_datetime == FORMAT_INITIAL_DATETIME_YYMMDDHHII
        # AND: Generate format_datetime Parameters
        assert imu_parser.format_datetime == FORMAT_DATETIME_SSFF
        # AND: Generate initial_data_packet_len Parameters
        assert imu_parser.initial_data_packet_len == EXPECTED_INITIAL_DATA_PACKET_LEN
        # AND: Generate data_packet_len Parameters
        assert imu_parser.data_packet_len == EXPECTED_DATA_PACKET_LEN

    def test_run(self):
        # Given: parsed and create ImuParser from imu_data
        imu_parser = ImuParser(imu_data=self.imu_data)

        # When: call run method
        im_df = imu_parser.run()
        im_df = im_df.reset_index()

        # Then: im_df should be equal EXPECTED_IM_DF
        assert im_df.equals(EXPECTED_IM_DF)
