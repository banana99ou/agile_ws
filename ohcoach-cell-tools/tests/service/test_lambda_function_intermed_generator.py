from unittest import mock

import pytest

from ohcoach_cell_tools.service.lambda_function_intermed_generator import lambda_handler

REGION = "us-east-1"
BUCKET = "test-bucket"
TEST_GP_FILE_PATH = "original/team_750/2022/08/19/CLBX-4B-42510_2.0_0_1660914714_0.gp"
TEST_IM_FILE_PATH = "original/team_750/2022/08/19/CLBX-4B-42510_2.0_0_1660914714_0.im"
TEST_DATA = "test-data"

event_gp = {
    "Records": [
        {
            "s3": {
                "bucket": {
                    "name": BUCKET,
                },
                "object": {
                    "key": TEST_GP_FILE_PATH,
                },
            }
        },
    ]
}
event_im = {
    "Records": [
        {
            "s3": {
                "bucket": {
                    "name": BUCKET,
                },
                "object": {
                    "key": TEST_IM_FILE_PATH,
                },
            }
        },
    ]
}


def get_gp_im_file_path(*args, **kwargs):
    if kwargs["file_path"].endswith(".gp"):
        return TEST_IM_FILE_PATH

    return TEST_GP_FILE_PATH


@pytest.fixture
def mock_paired_gp_im_files_exist():
    with mock.patch("ohcoach_cell_tools.common.aws_s3_helper.S3Helper.read_data") as mock_read_data:
        with mock.patch(
            "ohcoach_cell_tools.common.aws_s3_helper.S3Helper.find_paired_file",
            side_effect=get_gp_im_file_path,
        ) as mock_find_paired_file:
            yield mock_read_data, mock_find_paired_file


@mock.patch("ohcoach_cell_tools.common.aws_s3_helper.S3Helper.write_data")
class TestLambdaIntermedGenerator:
    @pytest.mark.usefixtures("mock_paired_gp_im_files_exist")
    def test_paired_gp_im_files_exist_when_gp_event_request(self, *_):
        # Given: gp, im file
        # When: call lambda_handler
        return_status = lambda_handler(event_gp, None)

        # Then: request success
        assert return_status == {"statusCode": 200}

    @pytest.mark.usefixtures("mock_paired_gp_im_files_exist")
    def test_paired_gp_im_files_exist_when_im_event_request(self, *_):
        # Given: gp, im file
        # When: call lambda_handler
        return_status = lambda_handler(event_im, None)

        # Then: request success
        assert return_status == {"statusCode": 200}

    def test_paired_gp_im_files_not_exist_when_gp_event_request(self, *_):
        # Given: gp file
        # When: call lambda_handler
        return_status = lambda_handler(event_gp, None)

        # Then: request fail
        assert return_status == {"statusCode": 404}

    def test_paired_gp_im_files_not_exist_when_im_event_request(self, *_):
        # Given: im file
        # When: call lambda_handler
        return_status = lambda_handler(event_im, None)

        # Then: request fail
        assert return_status == {"statusCode": 404}
