from unittest import mock

import boto3
import pytest
from moto import mock_s3

from ohcoach_cell_tools.common import aws_s3_helper

TEST_REGION_NAME = "us-east-1"
TEST_BUCKET_NAME = "test-bucket"
TEST_KEY = "test-key"
TEST_BODY = "test body test body please pass the test"


@pytest.fixture
def fake_s3():
    with mock_s3():
        conn = boto3.resource("s3", region_name=TEST_REGION_NAME)
        conn.create_bucket(Bucket=TEST_BUCKET_NAME)
        yield conn


class TestS3Helper:
    @pytest.fixture(autouse=True)
    def set_up_attr(self, fake_s3):
        setattr(aws_s3_helper, "s3", fake_s3)

    def test_read_data(self, fake_s3):
        # Given : test data upload
        obj = fake_s3.Object(bucket_name=TEST_BUCKET_NAME, key=TEST_KEY)
        obj.put(Body=TEST_BODY)

        # When : read test data
        response = aws_s3_helper.S3Helper.read_data(obj_name=TEST_KEY, bucket_name=TEST_BUCKET_NAME)

        # Then : compare test data
        assert response == TEST_BODY

    def test_fail_to_read_data(self):
        # When / Then : NoSuchKey Error
        with pytest.raises(Exception):
            aws_s3_helper.S3Helper.read_data(obj_name=TEST_KEY, bucket_name=TEST_BUCKET_NAME)

    def test_write_data(self, fake_s3):
        # When : write test body
        aws_s3_helper.S3Helper.write_data(
            obj_name=TEST_KEY, body=TEST_BODY, bucket_name=TEST_BUCKET_NAME
        )

        # Then : check data is exist on s3
        response = fake_s3.Object(bucket_name=TEST_BUCKET_NAME, key=TEST_KEY).get()
        assert response is not None

    @pytest.mark.parametrize(
        "request_file_path_key, paired_file_path_key",
        [
            (
                "intermed/team_221/2021/06/23/CLBX-3A-33104_3.2_0_1623302041_1_1.rgp",
                "intermed/team_221/2021/06/23/CLBX-3A-33104_3.2_0_1623302041_1_1.rim",
            ),
            (
                "intermed/team_221/2021/06/23/CLBX-3A-33104_3.2_0_1623302041_1_1.rim",
                "intermed/team_221/2021/06/23/CLBX-3A-33104_3.2_0_1623302041_1_1.rgp",
            ),
            (
                "intermed/team_221/2022/01/05/CLBX-4B-41561_2.0_0_1641270807_0.gp",
                "intermed/team_221/2022/01/05/CLBX-4B-41561_2.0_0_1641270807_0.im",
            ),
            (
                "intermed/team_221/2022/01/05/CLBX-4B-41561_2.0_0_1641270807_0.im",
                "intermed/team_221/2022/01/05/CLBX-4B-41561_2.0_0_1641270807_0.gp",
            ),
        ],
    )
    def test_success_to_find_paired_file(
        self, fake_s3, request_file_path_key, paired_file_path_key
    ):
        # Given : register request/paired files
        request_obj = fake_s3.Object(bucket_name=TEST_BUCKET_NAME, key=request_file_path_key)
        request_obj.put(Body=TEST_BODY)
        paired_obj = fake_s3.Object(bucket_name=TEST_BUCKET_NAME, key=paired_file_path_key)
        paired_obj.put(Body=TEST_BODY)

        # When : find paired file
        paired_file_path = aws_s3_helper.S3Helper.find_paired_file(
            request_file_path_key,
            TEST_BUCKET_NAME,
        )

        # Then : compare paired file path and paired file path key
        assert paired_file_path == paired_file_path_key

    @pytest.mark.parametrize(
        "request_file_path_key",
        [
            "intermed/team_221/2021/06/23/CLBX-3A-33104_3.2_0_1623302041_1_1.rgp",
            "intermed/team_221/2021/06/23/CLBX-3A-33104_3.2_0_1623302041_1_1.rim",
            "intermed/team_221/2022/01/05/CLBX-4B-41561_2.0_0_1641270807_0.gp",
            "intermed/team_221/2022/01/05/CLBX-4B-41561_2.0_0_1641270807_0.im",
        ],
    )
    def test_fail_to_find_paired_file(self, fake_s3, request_file_path_key):
        # Given : register request file
        request_obj = fake_s3.Object(bucket_name=TEST_BUCKET_NAME, key=request_file_path_key)
        request_obj.put(Body=TEST_BODY)

        # When : find paired file
        paired_file_path = aws_s3_helper.S3Helper.find_paired_file(
            request_file_path_key,
            TEST_BUCKET_NAME,
        )

        # Then : paired file path is None
        assert paired_file_path is None

    @pytest.mark.parametrize(
        "request_file_path_key",
        [
            "intermed/team_221/2021/06/23/CLBX-3A-33104_3.2_0_1623302041_1_1.rgp",
            "intermed/team_221/2021/06/23/CLBX-3A-33104_3.2_0_1623302041_1_1.rim",
            "intermed/team_221/2022/01/05/CLBX-4B-41561_2.0_0_1641270807_0.gp",
            "intermed/team_221/2022/01/05/CLBX-4B-41561_2.0_0_1641270807_0.im",
        ],
    )
    def test_client_error_when_get_object_names_function_called(
        self, fake_s3, request_file_path_key
    ):
        # Given : register request file
        request_obj = fake_s3.Object(bucket_name=TEST_BUCKET_NAME, key=request_file_path_key)
        request_obj.put(Body=TEST_BODY)

        with mock.patch(
            "ohcoach_cell_tools.common.aws_s3_helper.S3Helper.get_object_names",
        ) as mock_get_objects_names:
            # When : find paired function
            paired_file_path = aws_s3_helper.S3Helper.find_paired_file(
                request_file_path_key,
                "TEST_BUCKET_NAME",
            )

            # Then : paired file path is None
            assert paired_file_path is None
            mock_get_objects_names.assert_called_once()

    def test_determine_target_file_type_handling_error(self):
        # Given : register invalid request file
        request_file_path = "request-file-path.ftg"

        # When : raise file type error
        with pytest.raises(Exception):
            aws_s3_helper.S3Helper.find_paired_file(request_file_path, TEST_BUCKET_NAME)

    @pytest.mark.parametrize(
        "request_file_path_key, paired_file_path_key",
        [
            (
                "intermed/team_221/2021/06/23/CLBX-3A-33104_3.2_0_1623302041_1_1.rgp",
                "intermed/team_221/2021/06/23/CLBX-3A-33104_3.2_0_1623302041_1_1.rim",
            ),
            (
                "intermed/team_221/2021/06/23/CLBX-3A-33104_3.2_0_1623302041_1_1.rim",
                "intermed/team_221/2021/06/23/CLBX-3A-33104_3.2_0_1623302041_1_1.rgp",
            ),
            (
                "intermed/team_221/2022/01/05/CLBX-4B-41561_2.0_0_1641270807_0.gp",
                "intermed/team_221/2022/01/05/CLBX-4B-41561_2.0_0_1641270807_0.im",
            ),
            (
                "intermed/team_221/2022/01/05/CLBX-4B-41561_2.0_0_1641270807_0.im",
                "intermed/team_221/2022/01/05/CLBX-4B-41561_2.0_0_1641270807_0.gp",
            ),
        ],
    )
    def test_regex_above_x3_return_invalid_value(
        self, fake_s3, request_file_path_key, paired_file_path_key
    ):
        # Given : register request/paired files
        request_obj = fake_s3.Object(bucket_name=TEST_BUCKET_NAME, key=request_file_path_key)
        request_obj.put(Body=TEST_BODY)
        paired_obj = fake_s3.Object(bucket_name=TEST_BUCKET_NAME, key=paired_file_path_key)
        paired_obj.put(Body=TEST_BODY)

        # When : invalid regex
        paired_file_path = aws_s3_helper.S3Helper.find_paired_file(
            request_file_path_key.replace("intermed", "invalid"),
            TEST_BUCKET_NAME,
        )

        # Then : paired file path is None
        assert paired_file_path is None
