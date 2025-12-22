from ohcoach_cell_tools.common.aws_s3_helper import S3Helper


class GpImPublisher:
    @classmethod
    def make_file_name(cls, original_s3_key: str, extension: str) -> str:
        return original_s3_key.replace("ftg", extension)

    @classmethod
    def push_converted_data_to_s3(
        cls,
        contents: bytes,
        bucket_name: str,
        original_key: str,
        extension="gp",
    ) -> str:
        converted_file_name = cls.make_file_name(original_key, extension=extension)

        S3Helper.write_data(
            converted_file_name,
            contents,
            bucket_name=bucket_name,
        )

        return converted_file_name

    @staticmethod
    def fetch_cell_data_from_s3(bucket_name: str, file_key: str) -> bytes:
        if not file_key.endswith(".ftg"):
            raise Exception("wrong file extension")

        return S3Helper.read_data(file_key, bucket_name=bucket_name)
