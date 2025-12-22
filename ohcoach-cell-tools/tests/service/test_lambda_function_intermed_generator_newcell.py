import boto3
import numpy as np
import pandas as pd
import pytest
from moto import mock_s3

from ohcoach_cell_tools.common import aws_s3_helper
from ohcoach_cell_tools.service.lambda_function_intermed_generator_newcell import (
    lambda_handler,
    run,
)

wrong_file_content = (
    b"\xca`\x02\xe0\x01I"
    b"COACH\x04O\xceVLCXBA3\x03\x00\x31\x34\x39>\x00\xff\xff\xff\xffPolar OH1 8714ED23\x00\x00\x00\x00\x00\x00\x00\x00l\xbd\x00\x00\x00\x00\x00\x00\x02<)y\x96\xc0\x00\x00\x00\x00\xe5Y\xc6\xbf\x00\x00\x9b?\x00\x00\x00\x00\x00\x00\x9c?\xe2\r\n"
    b"COACH\x05\tNX\x017\x00\x02\x00&\x00\x08\r\n\xff@@DUMMY@DUMMY@DUMMY@@@@@@@DUMMY@DUMMY@DUMMY@DUMMY@DUMMY@@"
)

raw_bs_message_ble_not_connected = b"COACH\x03\x18\xe4\x07\x02\x13t\xdb\t\x01\x01\x00\x00\x00\x00\x00[\x01\xfe\xfe\x00\x00\x00\x00\x00\x00\x15\r\n"
raw_bs_message_ble_connected = b"COACH\x03\x18\xe4\x07\x02\x13t\xdb\t\x01\x01\x00\x00\x00\x00\x00[\x01\xfe\xfe\x07\x00\x00\x00\x00\x00\x12\r\n"
raw_end_message = b"COACH\x05\tNX\x017\x00\x02\x00&\x00\x08\r\n\xff@@DUMMY@DUMMY@DUMMY@@@@@@@DUMMY@DUMMY@DUMMY@DUMMY@DUMMY@@"

raw_ftg_base_content = (
    b"\xca`\x02\xe0\x01I"
    b"COACH\x04O\xceVLCXBA3\x03\x00\x31\x34\x39>\x00\xff\xff\xff\xffPolar OH1 8714ED23\x00\x00\x00\x00\x00\x00\x00\x00l\xbd\x00\x00\x00\x00\x00\x00\x02<)y\x96\xc0\x00\x00\x00\x00\xe5Y\xc6\xbf\x00\x00\x9b?\x00\x00\x00\x00\x00\x00\x9c?\xe2\r\n"
    b"COACH\x014\xe4\x07\x02\x13j\xdb\t\x01P\xcf\x02\x13W\x00\x00\x00(\xb3\xa7\xdb'\x01\x00\x00\xde\x13\x02\x00|\x15\xec\x13\xd6\x06\x00\x00Pr\x00\x00\x00\x00\xd1\x00\xda\x00\xaf\x00\x06\x06)A\x01\r\n"
    b"COACH\x02\x16j\xdb\t\x01\xff1\x00(\xf7\x1c\xff\x95\x00\x03\xff\xf7P\x01\xfc\x00\xa4\xfe6\r\n"
)

file_contents_bs_not_in_ble_connected_state = (
    raw_ftg_base_content + raw_bs_message_ble_not_connected + raw_end_message
)
file_contents = raw_ftg_base_content + raw_bs_message_ble_connected + raw_end_message

REGION = "us-east-1"
BUCKET = "cell-performance"
KEY = "original/team_221/2021/12/7/CLBX-3A-2222_3.0_0_1638443124_0.ftg"

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


class TestLambdaFucntionIntermedGeneratorNewcell:
    @pytest.fixture(autouse=True)
    def set_up_attr(self, fake_s3):
        setattr(aws_s3_helper, "s3", fake_s3)

    def test_run(self, fake_s3):
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

        # And: raw_data, rgp, rim and rbs files should be written
        raw_data_key = "raw_data/team_221/2021/12/7/CLBX-3A-2222_3.0_0_1638443124_0_1.csv"
        stored_raw_data_content = aws_s3_helper.S3Helper.read_data(raw_data_key, BUCKET)

        pd.testing.assert_frame_equal(
            pd.read_excel(stored_raw_data_content),
            pd.DataFrame(
                columns=["local_time", "latitude", "longitude", "speed(km/h)", "hr(bpm)"],
                data=[
                    [
                        "2020-02-20 02:42:32.100",
                        37.66351766666666,
                        127.1167588333333,
                        1.75,
                        np.NaN,
                    ]
                ],
            ),
        )

        rgp_key = "intermed/team_221/2021/12/7/CLBX-3A-2222_3.0_0_1638443124_0_1.rgp"
        stored_rgp_content = aws_s3_helper.S3Helper.read_data(rgp_key, BUCKET)

        assert stored_rgp_content == (
            "datetime,latitude,longitude,speed\n"
            "2020-02-19 17:42:32.100,37.663517666666664,127.11675883333334,1.75\n"
        )

        rim_key = "intermed/team_221/2021/12/7/CLBX-3A-2222_3.0_0_1638443124_0_1.rim"
        stored_rim_content = aws_s3_helper.S3Helper.read_data(rim_key, BUCKET)

        assert stored_rim_content == (
            "datetime,acc_x,acc_y,acc_z,gyro_x,gyro_y,gyro_z,magnet_x,magnet_y,magnet_z\n"
            "2020-02-19 17:42:32.100,-207,40,-2276,-107,3,-9,336,252,-348\n"
        )

        rbs_key = "intermed/team_221/2021/12/7/CLBX-3A-2222_3.0_0_1638443124_0_1.rbs"
        stored_rbs_content = aws_s3_helper.S3Helper.read_data(rbs_key, BUCKET)

        assert stored_rbs_content == (
            "datetime,operation_time,hr\n" "2020-02-19 17:42:32.200,1,0\n"
        )

    def test_run_when_rbs_contains_no_ble_connected_state(self, fake_s3):
        # Given: s3 data is stored
        obj = fake_s3.Object(bucket_name=BUCKET, key=KEY)
        obj.put(Body=file_contents_bs_not_in_ble_connected_state)

        # When: the lambda function is triggered: lambda_handler is called
        return_status = lambda_handler(event, None)

        # Then: request success
        assert return_status == {
            "statusCode": 200,
            "body": '"Done"',
        }

        raw_data_key = "raw_data/team_221/2021/12/7/CLBX-3A-2222_3.0_0_1638443124_0_1.csv"
        stored_raw_data_content = aws_s3_helper.S3Helper.read_data(raw_data_key, BUCKET)

        pd.testing.assert_frame_equal(
            pd.read_excel(stored_raw_data_content),
            pd.DataFrame(
                columns=["local_time", "latitude", "longitude", "speed(km/h)", "hr(bpm)"],
                data=[
                    [
                        "2020-02-20 02:42:32.100",
                        37.66351766666666,
                        127.1167588333333,
                        1.75,
                        np.NaN,
                    ]
                ],
            ),
        )

        # And: rgp and rim files should be written
        rgp_key = "intermed/team_221/2021/12/7/CLBX-3A-2222_3.0_0_1638443124_0_1.rgp"
        stored_rgp_content = aws_s3_helper.S3Helper.read_data(rgp_key, BUCKET)

        assert stored_rgp_content == (
            "datetime,latitude,longitude,speed\n"
            "2020-02-19 17:42:32.100,37.663517666666664,127.11675883333334,1.75\n"
        )

        rim_key = "intermed/team_221/2021/12/7/CLBX-3A-2222_3.0_0_1638443124_0_1.rim"
        stored_rim_content = aws_s3_helper.S3Helper.read_data(rim_key, BUCKET)

        assert stored_rim_content == (
            "datetime,acc_x,acc_y,acc_z,gyro_x,gyro_y,gyro_z,magnet_x,magnet_y,magnet_z\n"
            "2020-02-19 17:42:32.100,-207,40,-2276,-107,3,-9,336,252,-348\n"
        )

        # And: rbs file should not be written
        rbs_key = "intermed/team_221/2021/12/7/CLBX-3A-2222_3.0_0_1638443124_0_1.rbs"
        obj = fake_s3.Object(bucket_name=BUCKET, key=rbs_key)
        with pytest.raises(Exception) as e:
            obj.last_modified
        assert (
            str(e.value)
            == "An error occurred (404) when calling the HeadObject operation: Not Found"
        )

    def test_run_when_empty_dataframe(self, fake_s3):
        # Given: s3 data is stored
        obj = fake_s3.Object(bucket_name=BUCKET, key=KEY)
        obj.put(Body=wrong_file_content)

        # When: run function is called
        actual_parsing_errors = run(BUCKET, KEY)

        # Then: the "empty dataframe" error should be include
        assert len(actual_parsing_errors) == 1
        assert actual_parsing_errors[1][0].startswith(
            "[INTERMED-FTG] Empty dataframe(s), index : 1, start :"
        )
