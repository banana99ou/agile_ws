import boto3
import pytest
from moto import mock_s3

from ohcoach_cell_tools.common import aws_s3_helper
from ohcoach_cell_tools.publishers.gp_im_publisher import GpImPublisher
from tests.ftg_parser.converters.conversion_test_data import encoded_gps_result, encoded_im_result

file_contents = (
    b"\xca`\x02\xe0\x01I"
    b"COACH\x04O\xae\x08LCXBA3\x03\x00\x31\x34\x39\x15\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00\xa0\x9c\xbd\x00\x00|<\x00@\xeb\xbd\xee\x82\xbf\xc0/\xf8\xab>/\xf8\xab\xbf\x00\x80\x96?\x00\x80\x97?\x00\x80\x91?\xca\r\n"
    b"COACH\x014\xe4\x07\x02\x13j\xdb\t\x01P\xcf\x02\x13W\x00\x00\x00(\xb3\xa7\xdb'\x01\x00\x00\xde\x13\x02\x00|\x15\xec\x13\xd6\x06\x00\x00Pr\x00\x00\x00\x00\xd1\x00\xda\x00\xaf\x00\x06\x06)A\x01\r\n"
    b"COACH\x02\x16j\xdb\t\x01\xff1\x00(\xf7\x1c\xff\x95\x00\x03\xff\xf7P\x01\xfc\x00\xa4\xfe6\r\n"
    b"COACH\x03\x18\xe4\x07\x02\x13t\xdb\t\x01\x01\x00\x00\x00\x00\x00[\x01\xfe\xfe\x00\x00\x00\x00\x00\x00\x15\r\n"
    b"COACH\x05\tNX\x017\x00\x02\x00&\x00\x08\r\n\xff@@DUMMY@DUMMY@DUMMY@@@@@@@DUMMY@DUMMY@DUMMY@DUMMY@DUMMY@@"
)

REGION = "us-east-1"
BUCKET = "x1original"
KEY = "2022/02/07/CLBX-3A-2222_3.0_0_1638443124_0.ftg"


class TestGpImPublisher:
    @pytest.mark.parametrize(
        "original_s3_key, extension, expected_s3_key",
        [
            (
                "2022/02/07/CLBX-3A-2222_3.0_0_1638443124_0.ftg",
                "gp",
                "2022/02/07/CLBX-3A-2222_3.0_0_1638443124_0.gp",
            ),
            (
                "2022/02/07/CLBX-3A-2222_3.0_0_1638443124_0.ftg",
                "im",
                "2022/02/07/CLBX-3A-2222_3.0_0_1638443124_0.im",
            ),
        ],
    )
    def test_make_file_name(self, original_s3_key, extension, expected_s3_key):
        # When: call make_file_name on arguments
        actual_s3_key = GpImPublisher.make_file_name(original_s3_key, extension)

        # Then: result s3 key should be equal to expected s3 key
        assert actual_s3_key == expected_s3_key

    def test_fetch_cell_data_from_s3_when_file_extension_is_wrong(self):
        # Given: file key with wrong extension
        file_key = "2022/02/07/CLBX-3A-2222_3.0_0_1638443124_0.gp"

        # Then: call fetch_cell_data_from_s3 should raise an exception
        with pytest.raises(Exception, match="wrong file extension"):
            GpImPublisher.fetch_cell_data_from_s3(BUCKET, file_key)

    @mock_s3
    def test_fetch_cell_data_from_s3(self, monkeypatch):
        conn = boto3.resource("s3", region_name=REGION)
        conn.create_bucket(Bucket=BUCKET)

        # Given: s3 data is stored
        s3 = boto3.client("s3", region_name=REGION)
        s3.put_object(Bucket=BUCKET, Key=KEY, Body=file_contents)

        # And: mock aws_s3_helper.s3 with fack s3
        monkeypatch.setattr(aws_s3_helper, "s3", conn)

        # When: call fetch_cell_data_from_s3
        received_contents = GpImPublisher.fetch_cell_data_from_s3(BUCKET, KEY)

        # Then: s3 data is fetched
        assert received_contents == file_contents

    @mock_s3
    def test_push_converted_data_to_s3_for_gp_content(self, monkeypatch):
        conn = boto3.resource("s3", region_name=REGION)
        conn.create_bucket(Bucket=BUCKET)

        monkeypatch.setattr(aws_s3_helper, "s3", conn)

        # When: push_converted_data_to_s3 is called on encoded_gps_result
        returned_gp_key = GpImPublisher.push_converted_data_to_s3(
            encoded_gps_result,
            BUCKET,
            KEY,
            "gp",
        )

        # Then: gp file should be stored in S3
        expected_gp_key = KEY.replace("ftg", "gp")

        assert returned_gp_key == expected_gp_key

        stored_content = aws_s3_helper.S3Helper.read_data(returned_gp_key, BUCKET)

        assert bytes(stored_content, "utf-8") == encoded_gps_result

    @mock_s3
    def test_push_converted_data_to_s3_for_im_content(self, monkeypatch):
        conn = boto3.resource("s3", region_name=REGION)
        conn.create_bucket(Bucket=BUCKET)

        monkeypatch.setattr(aws_s3_helper, "s3", conn)

        # When: push_converted_data_to_s3 is called on encoded_im_result
        returned_im_key = GpImPublisher.push_converted_data_to_s3(
            encoded_im_result,
            BUCKET,
            KEY,
            "im",
        )

        # Then: im file should be stored in S3
        expected_im_key = KEY.replace("ftg", "im")

        assert returned_im_key == expected_im_key

        stored_content = aws_s3_helper.S3Helper.read_data(returned_im_key, BUCKET)

        assert stored_content == encoded_im_result
