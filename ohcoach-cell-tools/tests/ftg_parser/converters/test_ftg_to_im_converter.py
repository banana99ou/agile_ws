import pandas as pd
import pytest

from ohcoach_cell_tools.constants import IMU_EXPORT_COLUMNS
from ohcoach_cell_tools.ftg_parser.converters.ftg_to_im_converter import ImConverter
from tests.ftg_parser.converters.conversion_test_data import encoded_im_result, sample_imu_rows

imu_dataframe = pd.DataFrame(sample_imu_rows, columns=IMU_EXPORT_COLUMNS)
first_datetime = imu_dataframe.loc[0]["datetime"]


class TestImConverter:
    def test_get_bytes_length(self):
        expected = 125

        # When: call get_bytes_length on the imu_dataframe
        result = ImConverter.get_bytes_length(imu_dataframe)

        # Then: the calculated length should be eqaul to the expected length
        assert result == expected

    def test_encode_initial_datetime(self):
        expected = b"\x14\x04\x0b\x11*"

        # When: call encode_initial_datetime on the first datetime of imu_dataframe
        result = ImConverter.encode_initial_datetime(first_datetime)

        # Then: the result should be equal to initial datetime bytes
        assert result == expected

    def test_encode_initial_datetime_unpack(self):
        expected = (
            first_datetime.year % 100,
            first_datetime.month,
            first_datetime.day,
            first_datetime.hour,
            first_datetime.minute,
        )

        # When: Unpack initial datetime bytes
        result = ImConverter.initial_datetime_format.unpack(b"\x14\x04\x0b\x11*")

        # Then: the result should be equal to the first datetime of imu_dataframe
        assert result == expected

    def test_encode_imu_record(self):
        expected = b" R\xff6\x00'\xf7(\xff\x95\x00\x04\xff\xf7\x01M\x00\xf1\xfe\x9d"

        # When: call encode_imu_record on the first row of imu_dataframe
        result = ImConverter.encode_imu_record(imu_dataframe.loc[0])

        # Then: the encoded record shoud be equal to the expected bytes
        assert result == expected

    def test_encode_to_im_format_when_input_dataframe_is_empty(self):
        # When: call encode_to_im_format on an empty dataframe then an exception should raised
        with pytest.raises(Exception):
            ImConverter.encode_to_im_format(pd.DataFrame())

    def test_encode_to_im_format(self):
        # When: call encode_imu_recored on the imu_dataframe
        result = ImConverter.encode_to_im_format(imu_dataframe)

        # Then: the encoded bytearray should be equal to expected bytearray
        assert result == encoded_im_result
