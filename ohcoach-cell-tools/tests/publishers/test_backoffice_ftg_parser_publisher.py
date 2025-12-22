from datetime import datetime

import boto3
import pandas as pd
import pytest
from moto import mock_s3

from ohcoach_cell_tools.common import aws_s3_helper
from ohcoach_cell_tools.constants import BS_EXPORT_COLUMNS, GPS_EXPORT_COLUMNS, IMU_EXPORT_COLUMNS
from ohcoach_cell_tools.publishers.backoffice_ftg_parser_publisher import (
    BackOfficeFtgParserPublisher,
)
from tests.ftg_parser.converters.conversion_test_data import encoded_gps_result, encoded_im_result

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

exported_bs_rows = [
    (datetime(2020, 2, 19, 17, 42, 32, 200000), 1, 0, 3.47, 652.78, 5, 0, 0),
    (datetime(2020, 2, 19, 17, 42, 33, 100000), 2, 0, 3.47, 652.78, 7, 0, 0),
    (datetime(2020, 2, 19, 17, 42, 34, 100000), 3, 0, 3.47, 652.78, 0, 0, 0),
    (datetime(2020, 2, 19, 17, 42, 35, 100000), 4, 0, 3.47, 652.78, 1, 0, 0),
    (datetime(2020, 2, 19, 17, 42, 36, 100000), 5, 0, 3.46, 652.78, 2, 0, 0),
]

REGION = "us-east-1"
BUCKET = "backoffice-cell-data"
KEY = "original/CLBX-3A-2222_3.0_0_1638443124_0.ftg"

log_message = "[FTG-Lambda] Start - bucket_name: backoffice-cell-data, file_name: original/CLBX-4B-41562_5.5_0_1657695934_1.ftg"
log_timestamp = "20220722080901"
expected_log_message = "[FTG-Lambda] Start - bucket_name: backoffice-cell-data, file_name: original/CLBX-4B-41562_5.5_0_1657695934_1.ftg"


class TestIBackOfficeFtgParserPublisher:
    # key format: original/
    @pytest.mark.parametrize(
        "original_s3_key, index, category, extension, expected_s3_key",
        [
            (
                "original/CLBX-3A-2222_3.0_0_1638443124_0.ftg",
                1,
                "rgp",
                "csv",
                "parsed/CLBX-3A-2222_3.0_0_1638443124_0_rgp_1.csv",
            ),
            (
                "original/CLBX-3A-2222_3.0_0_1638443124_0.ftg",
                1,
                "rim",
                "csv",
                "parsed/CLBX-3A-2222_3.0_0_1638443124_0_rim_1.csv",
            ),
        ],
    )
    def test_ftg_make_file_name(self, original_s3_key, index, category, extension, expected_s3_key):
        # When: call make_file_name on arguments
        actual_s3_key = BackOfficeFtgParserPublisher.make_file_name(
            original_s3_key, index, category, extension, None
        )

        # Then: result s3 key should be equal to expected s3 key
        assert actual_s3_key == expected_s3_key

    def test_ftg_fetch_cell_data_from_s3_when_file_extension_is_wrong(self):
        # Given: file key with wrong extension
        file_key = "original/CLBX-3A-2222_3.0_0_1638443124_0.gp"

        # Then: call fetch_cell_data_from_s3 should raise an exception
        with pytest.raises(Exception, match="wrong file extension"):
            BackOfficeFtgParserPublisher.fetch_cell_data_from_s3("backoffice-cell-data", file_key)

    @mock_s3
    def test_ftg_fetch_cell_data_from_s3(self, monkeypatch):
        conn = boto3.resource("s3", region_name=REGION)
        conn.create_bucket(Bucket=BUCKET)

        # Given: s3 data is stored
        s3 = boto3.client("s3", region_name=REGION)
        s3.put_object(Bucket=BUCKET, Key=KEY, Body=file_contents)

        # And: mock aws_s3_helper.s3 with fack s3
        monkeypatch.setattr(aws_s3_helper, "s3", conn)

        # When: call fetch_cell_data_from_s3
        received_contents = BackOfficeFtgParserPublisher.fetch_cell_data_from_s3(BUCKET, KEY)

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
        returned_rgp_key = BackOfficeFtgParserPublisher.push_to_s3(
            BUCKET, KEY, 1, category="rgp", df=gps_df
        )

        # Then: rgp csv file should be stored in S3
        rgp_key = "parsed/CLBX-3A-2222_3.0_0_1638443124_0_rgp_1.csv"

        assert returned_rgp_key == rgp_key

        stored_content = aws_s3_helper.S3Helper.read_data(rgp_key, BUCKET)

        assert stored_content == (
            "datetime,nmea_latitude,nmea_longitude,latitude,longitude,speed,height,h_acc,v_acc,course_angle,vertical_velocity,hdop,vdop,tdop,navigation_satellites,tracked_satellites,avg_cn0,pos_mode\n"
            "2020-02-19 17:42:32.100,3739.81106,12707.00553,37.663517666666664,127.11675883333334,1.75,136.158,55.0,51.0,292.64,0.0,2.09,2.18,1.75,6,6,41,65\n"
            "2020-02-19 17:42:32.200,3739.81118,12707.00531,37.663519666666666,127.11675516666666,1.869,134.728,43.0,41.0,276.64,0.0,2.09,2.18,1.75,6,6,41,65\n"
        )

    @mock_s3
    def test_push_rim_dataframe_to_s3(self, monkeypatch):
        conn = boto3.resource("s3", region_name=REGION)
        conn.create_bucket(Bucket=BUCKET)

        monkeypatch.setattr(aws_s3_helper, "s3", conn)

        # Given: a imu dataframe with full list of columns
        imu_df = pd.DataFrame(exported_imu_rows, columns=IMU_EXPORT_COLUMNS)

        # When: push_dataframe_to_s3 is called
        returned_rim_key = BackOfficeFtgParserPublisher.push_to_s3(
            BUCKET, KEY, 1, category="rim", df=imu_df
        )

        # Then: imu csv file should be stored in S3
        rim_key = "parsed/CLBX-3A-2222_3.0_0_1638443124_0_rim_1.csv"

        assert returned_rim_key == rim_key

        stored_content = aws_s3_helper.S3Helper.read_data(rim_key, BUCKET)

        assert stored_content == (
            "datetime,acc_x,acc_y,acc_z,gyro_x,gyro_y,gyro_z,magnet_x,magnet_y,magnet_z\n"
            "2020-04-11 17:42:32.820,-202,39,-2264,-107,4,-9,333,241,-355\n"
            "2020-04-11 17:42:32.830,-205,42,-2271,-106,5,-8,333,241,-355\n"
            "2020-04-11 17:42:32.840,-205,42,-2272,-106,4,-8,333,241,-355\n"
            "2020-04-11 17:42:32.850,-205,40,-2279,-106,3,-7,333,241,-355\n"
            "2020-04-11 17:42:32.860,-202,42,-2280,-106,4,-8,333,241,-355\n"
        )

    @mock_s3
    def test_push_rbs_dataframe_to_s3(self, monkeypatch):
        conn = boto3.resource("s3", region_name=REGION)
        conn.create_bucket(Bucket=BUCKET)

        monkeypatch.setattr(aws_s3_helper, "s3", conn)

        # Given: a bs dataframe with full list of columns
        bs_df = pd.DataFrame(exported_bs_rows, columns=BS_EXPORT_COLUMNS)

        # When: push_dataframe_to_s3 is called
        returned_rbs_key = BackOfficeFtgParserPublisher.push_to_s3(
            BUCKET, KEY, 1, category="rbs", df=bs_df
        )

        # Then: imu csv file should be stored in S3
        rbs_key = "parsed/CLBX-3A-2222_3.0_0_1638443124_0_rbs_1.csv"

        assert returned_rbs_key == rbs_key

        stored_content = aws_s3_helper.S3Helper.read_data(rbs_key, BUCKET)

        assert stored_content == (
            "datetime,operation_time,hr,battery,cell_temperature,cell_state,reserve_2,reserve_3\n"
            "2020-02-19 17:42:32.200,1,0,3.47,652.78,5,0,0\n"
            "2020-02-19 17:42:33.100,2,0,3.47,652.78,7,0,0\n"
            "2020-02-19 17:42:34.100,3,0,3.47,652.78,0,0,0\n"
            "2020-02-19 17:42:35.100,4,0,3.47,652.78,1,0,0\n"
            "2020-02-19 17:42:36.100,5,0,3.46,652.78,2,0,0\n"
        )

    @pytest.mark.parametrize(
        "original_s3_key,  extension, expected_s3_key",
        [
            (
                "original/CLBX-3A-2222_3.0_0_1638443124_0.ftg",
                "gp",
                "parsed/CLBX-3A-2222_3.0_0_1638443124_0_1.gp",
            ),
            (
                "original/CLBX-3A-2222_3.0_0_1638443124_0.ftg",
                "im",
                "parsed/CLBX-3A-2222_3.0_0_1638443124_0_1.im",
            ),
        ],
    )
    def test_gp_im_make_file_name(self, original_s3_key, extension, expected_s3_key):
        # When: call make_file_name on arguments
        actual_s3_key = BackOfficeFtgParserPublisher.make_file_name(
            original_s3_key, 0, None, extension=extension, timestamp_log=None
        )

        # Then: result s3 key should be equal to expected s3 key
        assert actual_s3_key == expected_s3_key

    def test_gp_im_fetch_cell_data_from_s3_when_file_extension_is_wrong(self):
        # Given: file key with wrong extension
        file_key = "original/CLBX-3A-2222_3.0_0_1638443124_0.csv"

        # Then: call fetch_cell_data_from_s3 should raise an exception
        with pytest.raises(Exception, match="wrong file extension"):
            BackOfficeFtgParserPublisher.fetch_cell_data_from_s3(BUCKET, file_key)

    @mock_s3
    def test_gp_im_fetch_cell_data_from_s3(self, monkeypatch):
        conn = boto3.resource("s3", region_name=REGION)
        conn.create_bucket(Bucket=BUCKET)

        # Given: s3 data is stored
        s3 = boto3.client("s3", region_name=REGION)
        s3.put_object(Bucket=BUCKET, Key=KEY, Body=file_contents)

        # And: mock aws_s3_helper.s3 with fack s3
        monkeypatch.setattr(aws_s3_helper, "s3", conn)

        # When: call fetch_cell_data_from_s3
        received_contents = BackOfficeFtgParserPublisher.fetch_cell_data_from_s3(BUCKET, KEY)

        # Then: s3 data is fetched
        assert received_contents == file_contents

    @mock_s3
    def test_push_to_s3_for_gp_content(self, monkeypatch):
        conn = boto3.resource("s3", region_name=REGION)
        conn.create_bucket(Bucket=BUCKET)

        monkeypatch.setattr(aws_s3_helper, "s3", conn)

        # When: push_converted_data_to_s3 is called on encoded_gps_result
        returned_gp_key = BackOfficeFtgParserPublisher.push_to_s3(
            BUCKET,
            KEY,
            extension="gp",
            byt=encoded_gps_result,
        )

        # Then: gp file should be stored in S3
        expected_gp_key = "parsed/CLBX-3A-2222_3.0_0_1638443124_0_1.gp"

        assert returned_gp_key == expected_gp_key

        stored_content = aws_s3_helper.S3Helper.read_data(returned_gp_key, BUCKET)

        assert bytes(stored_content, "utf-8") == encoded_gps_result

    @mock_s3
    def test_push_to_s3_for_im_content(self, monkeypatch):
        conn = boto3.resource("s3", region_name=REGION)
        conn.create_bucket(Bucket=BUCKET)

        monkeypatch.setattr(aws_s3_helper, "s3", conn)

        # When: push_converted_data_to_s3 is called on encoded_im_result
        returned_im_key = BackOfficeFtgParserPublisher.push_to_s3(
            BUCKET,
            KEY,
            extension="im",
            byt=encoded_im_result,
        )

        # Then: im file should be stored in S3
        expected_im_key = "parsed/CLBX-3A-2222_3.0_0_1638443124_0_1.im"

        assert returned_im_key == expected_im_key

        stored_content = aws_s3_helper.S3Helper.read_data(returned_im_key, BUCKET)

        assert stored_content == encoded_im_result

    @pytest.mark.parametrize(
        "original_s3_key, extension,timestamp_log, expected_s3_key",
        [
            (
                "original/CLBX-3A-2222_3.0_0_1638443124_0.ftg",
                "log",
                "20220722080901",
                "log/CLBX-3A-2222_3.0_0_1638443124_0_20220722080901.log",
            )
        ],
    )
    def test_log_make_file_name(self, original_s3_key, extension, timestamp_log, expected_s3_key):
        # When: call make_file_name on arguments
        actual_s3_key = BackOfficeFtgParserPublisher.make_file_name(
            original_s3_key, 0, None, extension=extension, timestamp_log=timestamp_log
        )

        # Then: result s3 key should be equal to expected s3 key
        assert actual_s3_key == expected_s3_key

    @mock_s3
    def test_push_to_s3_for_log(self, monkeypatch):
        conn = boto3.resource("s3", region_name=REGION)
        conn.create_bucket(Bucket=BUCKET)

        monkeypatch.setattr(aws_s3_helper, "s3", conn)

        # When: push_converted_data_to_s3 is called on encoded_im_result
        returned_log_key = BackOfficeFtgParserPublisher.push_to_s3(
            BUCKET, KEY, extension="log", log_file=log_message, timestamp_log=log_timestamp
        )

        # Then: log file should be stored in S3
        expected_log_key = "log/CLBX-3A-2222_3.0_0_1638443124_0_20220722080901.log"

        assert returned_log_key == expected_log_key

        stored_content = aws_s3_helper.S3Helper.read_data(expected_log_key, BUCKET)
        assert stored_content == expected_log_message

        # AND: stored_content bucketname sholud be equal bucketname
        stored_content_bucket_name = (
            stored_content.split("bucket_name")[1].split(",")[0].split(":")[1].lstrip()
        )
        assert stored_content_bucket_name == BUCKET
