import pandas as pd

from ohcoach_cell_tools.constants import (
    BS_EXPORT_COLUMNS,
    GPS_EXPORT_COLUMNS,
    HEADER_RBS,
    HEADER_RGP,
    HEADER_RIM,
    LABEL_DATETIME,
)
from ohcoach_cell_tools.publishers.raw_data_publisher import RawDataPublisher

exported_gps_rows = pd.read_csv("tests/publishers/sample/test_rgp.csv")
exported_bs_rows = pd.read_csv("tests/publishers/sample/test_rbs.csv")
ORIGINAL_S3_FILE_KEY = "original/team_221/2021/12/7/CLBX-3A-2222_3.0_0_1638443124_0.ftg"
INDEX = 1


class TestRawDataPublisher:
    # key format: original/team_id/YYYY/MM/DD
    def test_make_file_name(self):
        # When: call RawDataPublisher
        raw_data_publisher = RawDataPublisher(
            pd.DataFrame(columns=HEADER_RGP),
            pd.DataFrame(columns=HEADER_RIM),
            pd.DataFrame(columns=HEADER_RBS),
            ORIGINAL_S3_FILE_KEY,
            INDEX,
        )

        # Then: result s3 key should be equal to expected s3 key
        assert (
            raw_data_publisher.raw_data_file_path
            == "raw_data/team_221/2021/12/7/CLBX-3A-2222_3.0_0_1638443124_0_1.csv"
        )

    def test_timezone(self):
        # Given: rgp_df
        rgp_df = exported_gps_rows[GPS_EXPORT_COLUMNS]
        rgp_df[LABEL_DATETIME] = pd.to_datetime(rgp_df[LABEL_DATETIME])

        # When: call RawDataPublisher
        raw_data_publisher = RawDataPublisher(
            rgp_df,
            pd.DataFrame(columns=HEADER_RIM),
            pd.DataFrame(columns=HEADER_RBS),
            ORIGINAL_S3_FILE_KEY,
            INDEX,
        )

        # Then: result tz info is Netherlands
        assert raw_data_publisher.tz == "Europe/Amsterdam"

    def test_raw_data_is_empty(self):
        # When: call RawDataPublisher
        raw_data_publisher = RawDataPublisher(
            pd.DataFrame(columns=HEADER_RGP),
            pd.DataFrame(columns=HEADER_RIM),
            pd.DataFrame(columns=HEADER_RBS),
            ORIGINAL_S3_FILE_KEY,
            INDEX,
        )

        # Then: result raw_data has rgp/rbs data
        assert raw_data_publisher.raw_data_dataframe.empty is True

    def test_raw_data_dataframe_when_rgp_rbs_exist(self):
        # Given: rgp_df
        rgp_df = exported_gps_rows[GPS_EXPORT_COLUMNS]
        rbs_df = exported_bs_rows[BS_EXPORT_COLUMNS]
        rgp_df[LABEL_DATETIME] = pd.to_datetime(rgp_df[LABEL_DATETIME])
        rbs_df[LABEL_DATETIME] = pd.to_datetime(rbs_df[LABEL_DATETIME])

        # When: call RawDataPublisher
        raw_data_publisher = RawDataPublisher(
            rgp_df,
            pd.DataFrame(columns=HEADER_RIM),
            rbs_df,
            ORIGINAL_S3_FILE_KEY,
            INDEX,
        )

        # Then: result raw_data has rgp/rbs data
        result = pd.read_csv("tests/publishers/sample/raw_data.csv")
        pd.testing.assert_frame_equal(raw_data_publisher.raw_data_dataframe.reset_index(), result)

    def test_raw_data_dataframe_when_rgp_exists(self):
        # Given: rgp_df
        rgp_df = exported_gps_rows[GPS_EXPORT_COLUMNS]
        rgp_df[LABEL_DATETIME] = pd.to_datetime(rgp_df[LABEL_DATETIME])

        # When: call RawDataPublisher
        raw_data_publisher = RawDataPublisher(
            rgp_df,
            pd.DataFrame(columns=HEADER_RIM),
            pd.DataFrame(columns=HEADER_RBS),
            ORIGINAL_S3_FILE_KEY,
            INDEX,
        )

        # Then: result raw_data has rgp/rbs data
        result = pd.read_csv("tests/publishers/sample/raw_data_only_rgp.csv").astype(
            {"hr(bpm)": object}
        )
        pd.testing.assert_frame_equal(raw_data_publisher.raw_data_dataframe.reset_index(), result)
