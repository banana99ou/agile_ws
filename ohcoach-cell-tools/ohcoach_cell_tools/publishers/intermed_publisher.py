import pandas as pd

from ohcoach_cell_tools.common.aws_s3_helper import S3Helper

ORIGINAL_DIR = "original"
INTERMED_DIR = "intermed"


class IntermedPublisher:
    @classmethod
    def make_file_name(cls, original_s3_key: str, index: int, extension: str) -> str:
        without_extension = original_s3_key.replace(ORIGINAL_DIR, INTERMED_DIR).replace(".ftg", "")

        return f"{without_extension}_{index}.{extension}"

    @classmethod
    def push_dataframe_to_s3(
        cls,
        dataframe: pd.DataFrame,
        bucket_name: str,
        original_key: str,
        index: int,
        columns: list,
        extension: str,
    ) -> str:
        intermed_file_name = cls.make_file_name(original_key, index, extension=extension)
        dataframe_with_selected_columns = dataframe[columns]

        S3Helper.write_data(
            intermed_file_name,
            dataframe_with_selected_columns.to_csv(index=False, sep=","),
            bucket_name=bucket_name,
        )

        return intermed_file_name

    @staticmethod
    def fetch_cell_data_from_s3(bucket_name: str, file_key: str) -> bytes:
        if not file_key.endswith(".ftg"):
            raise Exception("wrong file extension")

        return S3Helper.read_data(file_key, bucket_name=bucket_name)

    @classmethod
    def push_dataframe_to_s3_backoffice(
        cls,
        dataframe: pd.DataFrame,
        bucket_name: str,
        original_key: str,
        index: int,
        extension: str,
    ):
        intermed_file_name = f"{cls.make_file_name(original_key, index, extension=extension)}.csv"

        S3Helper.write_data(
            intermed_file_name,
            dataframe.to_csv(index=False, sep=","),
            bucket_name=bucket_name,
        )
