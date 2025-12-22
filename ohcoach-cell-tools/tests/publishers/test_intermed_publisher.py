from datetime import datetime

import boto3
import pandas as pd
import pytest
from moto import mock_s3

from ohcoach_cell_tools.common import aws_s3_helper
from ohcoach_cell_tools.constants import (
    GPS_EXPORT_COLUMNS,
    HEADER_RGP,
    HEADER_RIM,
    IMU_EXPORT_COLUMNS,
)
from ohcoach_cell_tools.publishers.intermed_publisher import IntermedPublisher

file_contents = (
    b"\xca`\x02\xe0\x01I"
    b"COACH\x04O\xae\x08LCXBA3\x03\x00\x31\x34\x39\x15\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00\xa0\x9c\xbd\x00\x00|<\x00@\xeb\xbd\xee\x82\xbf\xc0/\xf8\xab>/\xf8\xab\xbf\x00\x80\x96?\x00\x80\x97?\x00\x80\x91?\xca\r\n"
    b"COACH\x014\xe4\x07\x02\x13j\xdb\t\x01P\xcf\x02\x13W\x00\x00\x00(\xb3\xa7\xdb'\x01\x00\x00\xde\x13\x02\x00|\x15\xec\x13\xd6\x06\x00\x00Pr\x00\x00\x00\x00\xd1\x00\xda\x00\xaf\x00\x06\x06)A\x01\r\n"
    b"COACH\x02\x16j\xdb\t\x01\xff1\x00(\xf7\x1c\xff\x95\x00\x03\xff\xf7P\x01\xfc\x00\xa4\xfe6\r\n"
    b"COACH\x03\x18\xe4\x07\x02\x13t\xdb\t\x01\x01\x00\x00\x00\x00\x00[\x01\xfe\xfe\x00\x00\x00\x00\x00\x00\x15\r\n"
    b"COACH\x05\tNX\x017\x00\x02\x00&\x00\x08\r\n\xff@@DUMMY@DUMMY@DUMMY@@@@@@@DUMMY@DUMMY@DUMMY@DUMMY@DUMMY@@"
)

exported_gps_rows = [
    (
        datetime(2020, 2, 19, 17, 42, 32, 100000),
        3739.81106,
        12707.00553,
        37.663517666666664,
        127.11675883333334,
        1.75,
        136.158,
        55.0,
        51.0,
        292.64,
        0.0,
        2.09,
        2.18,
        1.75,
        6,
        6,
        41,
        65,
    ),
    (
        datetime(2020, 2, 19, 17, 42, 32, 200000),
        3739.81118,
        12707.00531,
        37.663519666666666,
        127.11675516666666,
        1.869,
        134.728,
        43.0,
        41.0,
        276.64,
        0.0,
        2.09,
        2.18,
        1.75,
        6,
        6,
        41,
        65,
    ),
]

exported_imu_rows = [
    (datetime(2020, 4, 11, 17, 42, 32, 820000), -202, 39, -2264, -107, 4, -9, 333, 241, -355),
    (datetime(2020, 4, 11, 17, 42, 32, 830000), -205, 42, -2271, -106, 5, -8, 333, 241, -355),
    (datetime(2020, 4, 11, 17, 42, 32, 840000), -205, 42, -2272, -106, 4, -8, 333, 241, -355),
    (datetime(2020, 4, 11, 17, 42, 32, 850000), -205, 40, -2279, -106, 3, -7, 333, 241, -355),
    (datetime(2020, 4, 11, 17, 42, 32, 860000), -202, 42, -2280, -106, 4, -8, 333, 241, -355),
]

REGION = "us-east-1"
BUCKET = "cell-performance"
KEY = "original/team_221/2021/12/7/CLBX-3A-2222_3.0_0_1638443124_0.ftg"


class TestIntermedPublisher:
    # key format: original/team_id/YYYY/MM/DD
    @pytest.mark.parametrize(
        "original_s3_key, index, extension, expected_s3_key",
        [
            (
                "original/team_221/2021/12/7/CLBX-3A-2222_3.0_0_1638443124_0.ftg",
                1,
                "rgp",
                "intermed/team_221/2021/12/7/CLBX-3A-2222_3.0_0_1638443124_0_1.rgp",
            ),
            (
                "original/team_221/2021/12/7/CLBX-3A-2222_3.0_0_1638443124_0.ftg",
                1,
                "rim",
                "intermed/team_221/2021/12/7/CLBX-3A-2222_3.0_0_1638443124_0_1.rim",
            ),
        ],
    )
    def test_make_file_name(self, original_s3_key, index, extension, expected_s3_key):
        # When: call make_file_name on arguments
        actual_s3_key = IntermedPublisher.make_file_name(original_s3_key, index, extension)

        # Then: result s3 key should be equal to expected s3 key
        assert actual_s3_key == expected_s3_key

    def test_fetch_cell_data_from_s3_when_file_extension_is_wrong(self):
        # Given: file key with wrong extension
        file_key = "original/team_221/2021/12/7/CLBX-3A-2222_3.0_0_1638443124_0.gp"

        # Then: call fetch_cell_data_from_s3 should raise an exception
        with pytest.raises(Exception, match="wrong file extension"):
            IntermedPublisher.fetch_cell_data_from_s3("cell-performance", file_key)

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
        received_contents = IntermedPublisher.fetch_cell_data_from_s3(BUCKET, KEY)

        # Then: s3 data is fetched
        assert received_contents == file_contents

    @mock_s3
    def test_push_rgp_dataframe_to_s3(self, monkeypatch):
        conn = boto3.resource("s3", region_name=REGION)
        conn.create_bucket(Bucket=BUCKET)

        monkeypatch.setattr(aws_s3_helper, "s3", conn)

        # Given: a gps dataframe with full list of columns
        gps_df = pd.DataFrame(exported_gps_rows, columns=GPS_EXPORT_COLUMNS)

        # When: push_dataframe_to_s3 is called
        IntermedPublisher.push_dataframe_to_s3(
            gps_df,
            BUCKET,
            KEY,
            1,
            HEADER_RGP,
            "rgp",
        )

        # Then: rgp file should be stored in S3
        rgp_key = "intermed/team_221/2021/12/7/CLBX-3A-2222_3.0_0_1638443124_0_1.rgp"
        stored_content = aws_s3_helper.S3Helper.read_data(rgp_key, BUCKET)

        assert stored_content == (
            "datetime,latitude,longitude,speed\n"
            "2020-02-19 17:42:32.100,37.663517666666664,127.11675883333334,1.75\n"
            "2020-02-19 17:42:32.200,37.663519666666666,127.11675516666666,1.869\n"
        )

    @mock_s3
    def test_push_rim_dataframe_to_s3(self, monkeypatch):
        conn = boto3.resource("s3", region_name=REGION)
        conn.create_bucket(Bucket=BUCKET)

        monkeypatch.setattr(aws_s3_helper, "s3", conn)

        # Given: a imu dataframe with full list of columns
        imu_df = pd.DataFrame(exported_imu_rows, columns=IMU_EXPORT_COLUMNS)

        # When: push_dataframe_to_s3 is called
        IntermedPublisher.push_dataframe_to_s3(
            imu_df,
            BUCKET,
            KEY,
            1,
            HEADER_RIM,
            "rim",
        )

        # Then: imu file should be stored in S3
        rim_key = "intermed/team_221/2021/12/7/CLBX-3A-2222_3.0_0_1638443124_0_1.rim"
        stored_content = aws_s3_helper.S3Helper.read_data(rim_key, BUCKET)

        assert stored_content == (
            "datetime,acc_x,acc_y,acc_z,gyro_x,gyro_y,gyro_z,magnet_x,magnet_y,magnet_z\n"
            "2020-04-11 17:42:32.820,-202,39,-2264,-107,4,-9,333,241,-355\n"
            "2020-04-11 17:42:32.830,-205,42,-2271,-106,5,-8,333,241,-355\n"
            "2020-04-11 17:42:32.840,-205,42,-2272,-106,4,-8,333,241,-355\n"
            "2020-04-11 17:42:32.850,-205,40,-2279,-106,3,-7,333,241,-355\n"
            "2020-04-11 17:42:32.860,-202,42,-2280,-106,4,-8,333,241,-355\n"
        )
