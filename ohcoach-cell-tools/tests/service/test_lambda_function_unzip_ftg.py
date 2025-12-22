from unittest import mock

import pytest

from ohcoach_cell_tools.service.lambda_function_unzip_ftg import lambda_handler

REGION = "us-east-1"
BUCKET = "test-bucket"
KEY = "original/team_221/2023/01/04/CLBX-4D-46429_5.11_0_1672672826_2.zip"

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
def mock_zip_data():
    with mock.patch("ohcoach_cell_tools.common.aws_s3_helper.S3Helper.read_data") as mock_data:
        with open("tests/service/CLBX-4D-46429_5.11_0_1672672826_2.zip", "rb") as file_data:
            mock_data.return_value = file_data.read()
            yield mock_data


@mock.patch("ohcoach_cell_tools.common.aws_s3_helper.S3Helper.write_data")
class TestLambdaUnzipFtg:
    @pytest.mark.usefixtures("mock_zip_data")
    def test_success_to_unzip_ftg(self, *_):
        # Given: mock_zip_data
        # When: call lambda_handler
        return_status = lambda_handler(event, None)

        # Then: request success
        assert return_status == {"statusCode": 200}

    @mock.patch("ohcoach_cell_tools.service.lambda_function_unzip_ftg.run", side_effect=Exception())
    def test_fail_to_unzip_ftg(self, *_):
        # Given: mock_zip_data
        # When: call lambda_handler
        return_status = lambda_handler(event, None)

        # Then: request success
        assert return_status == {"statusCode": 422}
