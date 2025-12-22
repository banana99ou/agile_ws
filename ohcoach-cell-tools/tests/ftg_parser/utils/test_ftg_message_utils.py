from datetime import datetime

import pandas as pd
import pytest

from ohcoach_cell_tools.constants import GPS_EXPORT_COLUMNS
from ohcoach_cell_tools.ftg_parser.utils.ftg_message_utils import (
    date_time_utc_to_datetime,
    get_datetime_third_decimal_place,
    get_filtered_dataframe,
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
        "A",
    )
]

exported_gps_rows_has_datetime_over_five_hours = [
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
        "A",
    ),
    (
        datetime(2020, 2, 19, 23, 42, 32, 100000),
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
        "A",
    ),
]

exported_gps_has_pos_mode_n_rows = [
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
        "A",
    ),
    (
        datetime(2020, 2, 19, 17, 42, 32, 200000),
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
        "N",
    ),
]


@pytest.mark.parametrize("date, time_utc", [(318900196, 17423220)])
def test_date_time_utc_to_datetime(date, time_utc):
    expected = datetime(2020, 2, 19, 17, 42, 32, 200000)

    # When: call date_time_utc_to_datetime
    result = date_time_utc_to_datetime(date, time_utc)

    # Then: the result should be equal to the expected datetime
    assert result == expected


def test_date_time_utc_to_datetime_date_attr_none():
    expected = datetime(1900, 1, 1, 17, 42, 32, 820000)

    # Given: int time_utc
    time_utc = 17423282

    # When: call date_time_utc_to_datetime without date attr
    result = date_time_utc_to_datetime(time_utc=time_utc)

    # Then: the result should be equal to the expected datetime
    assert result == expected


def test_get_datetime_third_decimal_place():
    expected = pd.DataFrame(exported_gps_rows, columns=GPS_EXPORT_COLUMNS)

    result = get_datetime_third_decimal_place(df=expected)

    assert result.loc[0, "datetime"] == "2020-02-19 17:42:32.100"


def test_get_datetime_third_decimal_place_when_df_is_empty():
    expected = pd.DataFrame(columns=GPS_EXPORT_COLUMNS)

    result = get_datetime_third_decimal_place(df=expected)

    assert result.empty is True


def test_get_filtered_dataframe():
    expected = pd.DataFrame(exported_gps_has_pos_mode_n_rows, columns=GPS_EXPORT_COLUMNS)

    result = get_filtered_dataframe(df=expected)

    assert result.loc[1, "speed"] == 0


def test_get_filtered_dataframe_when_df_is_empty():
    expected = pd.DataFrame(columns=GPS_EXPORT_COLUMNS)

    result = get_datetime_third_decimal_place(df=expected)

    assert result.empty is True
