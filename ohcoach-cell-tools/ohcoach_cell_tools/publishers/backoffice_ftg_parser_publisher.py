from typing import Optional

import pandas as pd

from ohcoach_cell_tools.common.aws_s3_helper import S3Helper

ORIGINAL_DIR = "original"
PARSED_DIR = "parsed"
LOG_DIR = "log"
CHANGE_DIR = {"csv": PARSED_DIR, "gp": PARSED_DIR, "im": PARSED_DIR, "log": LOG_DIR}


class BackOfficeFtgParserPublisher:
    @classmethod
    def make_file_name(
        cls,
        original_s3_key: str,
        index: int,
        category: Optional[str],
        extension: str,
        timestamp_log: Optional[str],
    ) -> str:
        without_extension = original_s3_key.replace(ORIGINAL_DIR, CHANGE_DIR[extension]).replace(
            ".ftg", ""
        )
        if index:
            return f"{without_extension}_{category}_{index}.{extension}"
        if timestamp_log:
            return f"{without_extension}_{timestamp_log}.{extension}"
        return f"{without_extension}_{index + 1}.{extension}"

    @classmethod
    def push_to_s3(
        cls,
        bucket_name: str,
        original_key: str,
        index: int = 0,
        category: Optional[str] = None,
        extension: str = "csv",
        df: pd.DataFrame = pd.DataFrame(),
        byt: Optional[bytes] = None,
        log_file: Optional[str] = None,
        timestamp_log: Optional[str] = None,
    ) -> str:
        parsed_file_name = cls.make_file_name(
            original_key, index, category, extension, timestamp_log
        )

        print(f"{category if category else extension}_{index}: {parsed_file_name}")
        S3Helper.write_data(
            parsed_file_name,
            byt if byt else log_file if log_file else df.to_csv(index=False, sep=","),
            bucket_name=bucket_name,
        )

        return parsed_file_name

    @staticmethod
    def fetch_cell_data_from_s3(bucket_name: str, file_key: str) -> bytes:
        if not file_key.endswith(".ftg"):
            raise Exception("wrong file extension")

        return S3Helper.read_data(file_key, bucket_name=bucket_name)
