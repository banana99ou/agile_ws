import pytest
from sample_data.intermed_generator_sample_data import (
    TEST_GP_DATA,
    TEST_GP_TO_RGP_DF,
    TEST_GP_TO_RGP_DF_2,
    TEST_IM_DATA,
    TEST_IM_FILE_PATH,
    TEST_IM_TO_RIM_DF,
    TEST_IM_TO_RIM_DF_2,
)

from ohcoach_cell_tools.gp_im_parser.generators.intermed_generator import IntermedGenerator
from ohcoach_cell_tools.gp_im_parser.utils.cell_info_utils import CellInfo

TEST_RGP_DATA = {
    0: {
        "df": TEST_GP_TO_RGP_DF,
        "postfix": "_1.rgp",
    },
    1: {
        "df": TEST_GP_TO_RGP_DF_2,
        "postfix": "_2.rgp",
    },
}
TEST_RIM_DATA = {
    0: {
        "postfix": "_1.rim",
        "df": TEST_IM_TO_RIM_DF,
    },
    1: {
        "postfix": "_2.rim",
        "df": TEST_IM_TO_RIM_DF_2,
    },
}

EXPECTED_TIMEZONE = "None"
EXPECTED_RGP_DATA_LIST = []
EXPECTED_RIM_DATA_LIST = []


class TestIntermedGenerator:
    @pytest.fixture(autouse=True)
    def set_up(self):
        # Given : initialize Intermed Generator
        self.intermed_generator = IntermedGenerator(
            cell_info=CellInfo(file_path=TEST_IM_FILE_PATH),
            gp_data=TEST_GP_DATA,
            im_data=TEST_IM_DATA,
        )

    def test_gp_to_rgp(self):
        # When : call gp_to_rgp func
        self.intermed_generator.gp_to_rgp()
        rgp_data = self.intermed_generator.rgp_data_list

        # Then : compare result
        for idx, rgp in enumerate(rgp_data):
            rgp.df = rgp.df.astype(str)
            rgp.df = rgp.df.reset_index()

            assert rgp.postfix == TEST_RGP_DATA[idx]["postfix"]
            assert rgp.df.equals(TEST_RGP_DATA[idx]["df"])

    def test_im_to_rim(self):
        # When : call im_to_rgp func
        self.intermed_generator.im_to_rim()
        rim_data = self.intermed_generator.rim_data_list

        # Then : compare result
        for idx, rim in enumerate(rim_data):
            rim.df = rim.df.astype(str)
            rim.df = rim.df.reset_index()

            assert rim.postfix == TEST_RIM_DATA[idx]["postfix"]
            assert rim.df.equals(TEST_RIM_DATA[idx]["df"])

    def test_get_rgp_data_list(self):
        # When: call rgp_data_list property
        result = self.intermed_generator.rgp_data_list

        # Then: result should be equal EXPECTED_RGP_DATA_LIST
        assert result == EXPECTED_RGP_DATA_LIST

    def test_get_rim_data_list(self):
        # When: call rim_data_list property
        result = self.intermed_generator.rim_data_list

        # Then: result should be equal EXPECTED_RIM_DATA_LIST
        assert result == EXPECTED_RIM_DATA_LIST
