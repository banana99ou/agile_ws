from unittest.mock import patch

import boto3
import pytest
from moto import mock_s3

from ohcoach_cell_tools.common import aws_s3_helper
from ohcoach_cell_tools.common.web1_api_helper import Web1ApiHelper
from ohcoach_cell_tools.service.lambda_function_ftg_to_gp_im_converter import lambda_handler

file_contents = (
    b"\xca`\x02\xe0\x01I"
    b"COACH\x04O\xceVLCXBA3\x03\x00\x31\x34\x39>\x00\xff\xff\xff\xffPolar OH1 8714ED23\x00\x00\x00\x00\x00\x00\x00\x00l\xbd\x00\x00\x00\x00\x00\x00\x02<)y\x96\xc0\x00\x00\x00\x00\xe5Y\xc6\xbf\x00\x00\x9b?\x00\x00\x00\x00\x00\x00\x9c?\xe2\r\n"
    b"COACH\x014\xe4\x07\x02\x13j\xdb\t\x01P\xcf\x02\x13W\x00\x00\x00(\xb3\xa7\xdb'\x01\x00\x00\xde\x13\x02\x00|\x15\xec\x13\xd6\x06\x00\x00Pr\x00\x00\x00\x00\xd1\x00\xda\x00\xaf\x00\x06\x06)A\x01\r\n"
    b"COACH\x02\x16j\xdb\t\x01\xff1\x00(\xf7\x1c\xff\x95\x00\x03\xff\xf7P\x01\xfc\x00\xa4\xfe6\r\n"
    b"COACH\x03\x18\xe4\x07\x02\x13t\xdb\t\x01\x01\x00\x00\x00\x00\x00[\x01\xfe\xfe\x00\x00\x00\x00\x00\x00\x15\r\n"
    b"COACH\x05\tNX\x017\x00\x02\x00&\x00\x08\r\n\xff@@DUMMY@DUMMY@DUMMY@@@@@@@DUMMY@DUMMY@DUMMY@DUMMY@DUMMY@@"
)

file_contents_second = (
    b"COACH\x04O\xceVLCXBA3\x03\x00\x31\x34\x39>\x00\xff\xff\xff\xffPolar OH1 8714ED23\x00\x00\x00\x00\x00\x00\x00\x00l\xbd\x00\x00\x00\x00\x00\x00\x02<)y\x96\xc0\x00\x00\x00\x00\xe5Y\xc6\xbf\x00\x00\x9b?\x00\x00\x00\x00\x00\x00\x9c?\xe2\r\n"
    b"COACH\x014\xe4\x07\x02\x13j\xdb\t\x01P\xcf\x02\x13W\x00\x00\x00(\xb3\xa7\xdb'\x01\x00\x00\xde\x13\x02\x00|\x15\xec\x13\xd6\x06\x00\x00Pr\x00\x00\x00\x00\xd1\x00\xda\x00\xaf\x00\x06\x06)A\x01\r\n"
    b"COACH\x02\x16j\xdb\t\x01\xff1\x00(\xf7\x1c\xff\x95\x00\x03\xff\xf7P\x01\xfc\x00\xa4\xfe6\r\n"
    b"COACH\x03\x18\xe4\x07\x02\x13t\xdb\t\x01\x01\x00\x00\x00\x00\x00[\x01\xfe\xfe\x00\x00\x00\x00\x00\x00\x15\r\n"
    b"COACH\x05\tNX\x017\x00\x02\x00&\x00\x08\r\n\xff@@DUMMY@DUMMY@DUMMY@@@@@@@DUMMY@DUMMY@DUMMY@DUMMY@DUMMY@@"
)

REGION = "us-east-1"
BUCKET = "x1original"
KEY = "2022/02/07/CLBX-3A-2222_3.0_0_1638443124_0.ftg"
GP_KEY = KEY.replace("ftg", "gp")
IM_KEY = KEY.replace("ftg", "im")

event = {
    "Records": [
        {
            "s3": {
                "bucket": {
                    "name": BUCKET,
                },
                "object": {
                    "key": KEY,
                },
            }
        },
    ]
}


@pytest.fixture
def fake_s3():
    with mock_s3():
        conn = boto3.resource("s3", region_name=REGION)
        conn.create_bucket(Bucket=BUCKET)
        yield conn


@patch.object(Web1ApiHelper, "update_db_original_data_from_ftg")
class TestLambdaFunctionFtgToGpImConverter:
    @pytest.fixture(autouse=True)
    def set_up_attr(self, fake_s3):
        setattr(aws_s3_helper, "s3", fake_s3)

    def test_run_when_ftg_contains_only_one_start_end(self, _, fake_s3):
        # Given: s3 data is stored
        obj = fake_s3.Object(bucket_name=BUCKET, key=KEY)
        obj.put(Body=file_contents)

        # When: the lambda function is triggered: lambda_handler is called
        return_status = lambda_handler(event, None)

        # Then: request success
        assert return_status == {
            "statusCode": 200,
            "body": '"Done"',
        }

        # And: gp and im files should be written
        stored_gp_content = aws_s3_helper.S3Helper.read_data(GP_KEY, BUCKET)

        assert stored_gp_content == (
            "start$GPRMC,174232.10,A,3739.81106,N,12707.00553,E,0.945,,190220,,,A*70"
        )

        stored_im_content = aws_s3_helper.S3Helper.read_data(IM_KEY, BUCKET)

        assert stored_im_content == (
            b"100,-0.013672,0.019470,-0.078003,-1.725191,2.824427,-0.946565,1.191406,1.195312,1.156250BIAS..END\r\n\r\n"
            b"start20\x14\x02\x13\x11* \n\xff1\x00(\xf7\x1c\xff\x95\x00\x03\xff\xf7\x01P\x00\xfc\xfe\xa4"
        )

    def test_run_when_ftg_contains_two_start_end_pairs(self, _, fake_s3):
        # Given: s3 data is stored (the contents consists of two sections (2 start-end pair))
        obj = fake_s3.Object(bucket_name=BUCKET, key=KEY)
        obj.put(Body=file_contents + file_contents_second)

        # When: the lambda function is triggered: lambda_handler is called
        return_status = lambda_handler(event, None)

        # Then: request success
        assert return_status == {
            "statusCode": 200,
            "body": '"Done"',
        }

        # And: gp and im files should be written
        stored_gp_content = aws_s3_helper.S3Helper.read_data(GP_KEY, BUCKET)

        assert stored_gp_content == (
            "start$GPRMC,174232.10,A,3739.81106,N,12707.00553,E,0.945,,190220,,,A*70"
            "start$GPRMC,174232.10,A,3739.81106,N,12707.00553,E,0.945,,190220,,,A*70"
        )

        stored_im_content = aws_s3_helper.S3Helper.read_data(IM_KEY, BUCKET)

        assert stored_im_content == (
            b"100,-0.013672,0.019470,-0.078003,-1.725191,2.824427,-0.946565,1.191406,1.195312,1.156250BIAS..END\r\n\r\n"
            b"start20\x14\x02\x13\x11* \n\xff1\x00(\xf7\x1c\xff\x95\x00\x03\xff\xf7\x01P\x00\xfc\xfe\xa4BIAS..END"
            b"\r\n\r\nstart20\x14\x02\x13\x11* \n\xff1\x00(\xf7\x1c\xff\x95\x00\x03\xff\xf7\x01P\x00\xfc\xfe\xa4"
        )

    def test_run_function_calls_the_essential_api(self, mock_register_to_essential_server, fake_s3):
        mock_register_to_essential_server.return_value = {
            "status": 200,
            "msg": "2 files Success",
            "data": None,
        }

        # Given: s3 data is stored
        obj = fake_s3.Object(bucket_name=BUCKET, key=KEY)
        obj.put(Body=file_contents)

        # When: the lambda function is triggered: lambda_handler is called
        return_status = lambda_handler(event, None)

        # Then: register_to_essential_server method should be called once with proper arguments
        assert return_status == {
            "statusCode": 200,
            "body": '"Done"',
        }

        mock_register_to_essential_server.assert_called_once_with(
            "2022/02/07/CLBX-3A-2222_3.0_0_1638443124_0.ftg",
            "2022/02/07/CLBX-3A-2222_3.0_0_1638443124_0.gp",
            "2022/02/07/CLBX-3A-2222_3.0_0_1638443124_0.im",
        )
