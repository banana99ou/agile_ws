import pandas as pd

from ohcoach_cell_tools.constants import HEADER_OCH
from ohcoach_cell_tools.gp_im_parser.converters.gp_to_och_converter import GpToOchConverter
from tests.gp_im_parser.converters.gp_sample_data import gp

expected_och_row = [
    ("2022-07-29 06:44:43.000", 36.441869, 127.40976116666667, 0.07037600000000001),
    ("2022-07-29 06:44:43.100", 36.4418685, 127.40975966666667, 0.227796),
    (
        "2022-07-29 06:44:43.200",
        36.44186833333333,
        127.40975883333333,
        0.07408000000000001,
    ),
    ("2022-07-29 06:44:43.300", 36.441868, 127.409758, 0.02778),
    (
        "2022-07-29 06:44:43.400",
        36.44186766666667,
        127.40975733333333,
        0.12408400000000001,
    ),
    ("2022-07-29 06:44:43.500", 36.4418675, 127.4097565, 0.1389),
    ("2022-07-29 06:44:43.600", 36.441867333333334, 127.40975616666667, 0.105564),
    (
        "2022-07-29 06:44:43.700",
        36.441867333333334,
        127.40975616666667,
        0.18520000000000003,
    ),
    (
        "2022-07-29 06:44:43.800",
        36.44186716666667,
        127.40975583333334,
        0.04630000000000001,
    ),
    ("2022-07-29 06:44:43.900", 36.441867, 127.4097555, 0.135196),
    ("2022-07-29 06:44:44.000", 36.441867, 127.4097555, 0.035188000000000004),
    ("2022-07-29 06:44:44.100", 36.441867, 127.40975533333334, 0.061116000000000004),
    (
        "2022-07-29 06:44:44.200",
        36.441866833333336,
        127.409755,
        0.051856000000000006,
    ),
    ("2022-07-29 06:44:44.300", 36.44186666666667, 127.40975466666667, 0.050004),
]


class TestGoToOchConverter:
    def test_convert(self):
        expected_df = pd.DataFrame(expected_och_row, columns=HEADER_OCH)
        # Given: Declaring a Class
        go_to_och_converter = GpToOchConverter()

        # When: call convert method
        och_df = go_to_och_converter.convert(gp)
        och_df = och_df.reset_index()

        # Then: och_df should be equal expected_df
        assert expected_df.equals(och_df)
