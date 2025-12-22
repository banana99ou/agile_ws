import io
from typing import Optional

import pandas as pd
import pytz
from timezonefinder import TimezoneFinder

from ohcoach_cell_tools.common.aws_s3_helper import S3Helper
from ohcoach_cell_tools.constants import (
    BS_EXPORT_COLUMNS,
    HEADER_RAW_DATA,
    LABEL_DATETIME,
    LABEL_HR,
    LABEL_LATITUDE,
    LABEL_LOCALTIME,
    LABEL_LONGITUDE,
    LABEL_SPEED,
)
from ohcoach_cell_tools.ftg_parser.managers.bs_message_manager import BsMessageManager
from ohcoach_cell_tools.ftg_parser.utils.ftg_message_utils import get_datetime_third_decimal_place

ORIGINAL_DIR = "original"
RAW_DATA_DIR = "raw_data"


class RawDataPublisher:
    def __init__(
        self,
        rgp_df: pd.DataFrame,
        rim_df: pd.DataFrame,
        rbs_df: pd.DataFrame,
        original_file_path: str,
        index: int,
    ):
        self.rgp_df = rgp_df
        self.rim_df = rim_df
        self.rbs_df = (
            rbs_df
            if BsMessageManager.check_ble_connected(rbs_df)
            else pd.DataFrame(columns=BS_EXPORT_COLUMNS)
        )
        self.original_file_path = original_file_path
        self.index = index

    def __make_file_name(self, original_s3_key: str, index: int) -> str:
        without_extension = original_s3_key.replace(ORIGINAL_DIR, RAW_DATA_DIR).replace(".ftg", "")

        return f"{without_extension}_{index}.csv"

    def __get_local_timezone(self, rgp_df: pd.DataFrame) -> Optional[str]:
        local_zone = TimezoneFinder().timezone_at(
            lng=rgp_df[LABEL_LONGITUDE].mean(), lat=rgp_df[LABEL_LATITUDE].mean()
        )

        return pytz.timezone(zone=local_zone).zone if local_zone is not None else None

    @property
    def raw_data_file_path(self) -> str:
        return self.__make_file_name(self.original_file_path, self.index)

    @property
    def tz(self) -> Optional[str]:
        return self.__get_local_timezone(rgp_df=self.rgp_df)

    def __convert_local_timezone(self, df: pd.DataFrame) -> pd.DataFrame:
        if not df.empty:
            tz = self.tz
            df[LABEL_DATETIME] = df[LABEL_DATETIME].apply(
                lambda x: x.tz_localize("UTC").astimezone(tz=tz).replace(tzinfo=None)
            )

        return get_datetime_third_decimal_place(df=df)

    # TODO : datetime duplicate check
    @property
    def raw_data_dataframe(self) -> pd.DataFrame:
        df = pd.merge(self.rgp_df, self.rbs_df, on=LABEL_DATETIME, how="left")
        df = self.__convert_local_timezone(df=df)
        df.rename(
            columns={
                LABEL_DATETIME: LABEL_LOCALTIME,
                LABEL_SPEED: f"{LABEL_SPEED}(km/h)",
                LABEL_HR: f"{LABEL_HR}(bpm)",
            },
            inplace=True,
        )

        return df[HEADER_RAW_DATA].set_index(LABEL_LOCALTIME)

    def push_dataframe_to_s3(self, bucket_name: str) -> str:
        with io.BytesIO() as output:
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                self.raw_data_dataframe.to_excel(writer)
            data = output.getvalue()

        S3Helper.write_data(
            obj_name=self.raw_data_file_path,
            body=data,
            bucket_name=bucket_name,
        )

        return self.raw_data_file_path
