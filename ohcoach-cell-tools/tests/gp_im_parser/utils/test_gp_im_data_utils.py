from datetime import datetime

import pandas as pd

from ohcoach_cell_tools.gp_im_parser.utils.gp_im_data_utils import (
    ImuData,
    ReadableGPSData,
    ReadableIMUData,
)
from tests.gp_im_parser.imu_parser_sample_data import TEST_IM_STREAM

col_name = ["dataetime", "lat", "lon", "speed"]
data_row = [(datetime(2022, 8, 2, 7, 40, 00, 100000), 36.4418685, 127.40975966666667, 0.227796)]

df = pd.DataFrame(data_row, columns=col_name)
gps_postfix = "_0.rgp"
imu_postfix = "_0.rim"

device_version = "3A"
firmware_version = "3.0"
frequency = 100


class TestReadableGPSData:
    def test_get_readable_gps_data(self):
        # When: call ReadableGPSData
        rgp_data = ReadableGPSData(df=df, postfix=gps_postfix)

        # Then: Generate df Parameters
        assert rgp_data.df.equals(df)
        # AND: Generate postfix Parameters
        assert rgp_data.postfix == gps_postfix
        # AND: Generate file_path Parameters
        assert rgp_data.file_path is None


class TestReadableIMUData:
    def test_get_readable_imu_data(self):
        # When: call ReadableGPSData
        rgp_data = ReadableIMUData(df=df, postfix=imu_postfix)

        # Then: Generate df Parameters
        assert rgp_data.df.equals(df)
        # AND: Generate postfix Parameters
        assert rgp_data.postfix == imu_postfix
        # AND: Generate file_path Parameters
        assert rgp_data.file_path is None


class TestImuData:
    def test_get_imu_data(self):
        # When: call ImuData
        imu_data = ImuData(
            im_stream=TEST_IM_STREAM,
            device_version=device_version,
            firmware_version=firmware_version,
            frequency=frequency,
        )

        # Then: Generate im_stream Parameters
        assert imu_data.im_stream == TEST_IM_STREAM
        # AND: Generate device_version Parameters
        assert imu_data.device_version == device_version
        # AND: Generate firmware_version Parameters
        assert imu_data.firmware_version == firmware_version
        # AND: Generate frequency Parameters
        assert imu_data.frequency == frequency
