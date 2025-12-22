import os
import re
from enum import Enum
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError

from ohcoach_cell_tools.common.logger import Logger

s3 = boto3.resource("s3")


class TargetFileType(Enum):
    gp = "im"
    im = "gp"
    rim = "rgp"
    rgp = "rim"

    def __str__(self):
        return self.value


class S3Helper:
    logger = Logger("S3Helper")

    @staticmethod
    def get_object_names(
        prefix: str, bucket_name: Optional[str] = os.getenv("ENV_S3_BUCKET")
    ) -> list:
        try:
            bucket = s3.Bucket(bucket_name)
            return [obj.key for obj in bucket.objects.filter(Prefix=prefix).all()]
        except ClientError:
            S3Helper.logger.exception("Error from get_object_names()")
            return []

    @staticmethod
    def get_team_list(prefix: str, bucket_name: Optional[str] = os.getenv("ENV_S3_BUCKET")) -> list:
        try:
            bucket = s3.meta.client.list_objects_v2(
                Bucket=bucket_name, Prefix=prefix, Delimiter="/"
            )
            return [obj["Prefix"].split("/")[1] for obj in bucket["CommonPrefixes"]]
        except ClientError:
            S3Helper.logger.exception("Error from get_object_names()")
            return []

    @staticmethod
    def read_data(obj_name: str, bucket_name: Optional[str] = os.getenv("ENV_S3_BUCKET")):
        obj = s3.Object(bucket_name=bucket_name, key=obj_name)
        response = obj.get()
        body = response["Body"].read()
        try:
            return body.decode("utf-8")
        except ValueError:
            return body

    @staticmethod
    def write_data(
        obj_name: str, body: Any, bucket_name: Optional[str] = os.getenv("ENV_S3_BUCKET")
    ):
        obj = s3.Object(bucket_name=bucket_name, key=obj_name)
        response = obj.put(Body=body, StorageClass="INTELLIGENT_TIERING")

        if (status := response["ResponseMetadata"]["HTTPStatusCode"]) != 200:
            raise Exception(f"Error S3 Service - {status}")

    @staticmethod
    def find_paired_file(
        file_path: str, bucket_name: Optional[str] = os.getenv("ENV_S3_BUCKET")
    ) -> Optional[str]:
        def __determine_target_file_type():
            try:
                return TargetFileType[file_type]
            except Exception:
                S3Helper.logger.error(f"Invalid file type = {file_type}")

        def regex_above_X3():
            serial_number, firmware_version, _, timestamp, _ = object_name.split("_", 4)
            return re.compile(
                rf"(.*)/(.*)/{serial_number}_{firmware_version}_(.*)_{timestamp}_(.*)\.{target_file_type}"
            )

        def regex_below_X2():
            (
                production_number,
                firmware_version,
                _,
                extract_date,
                extract_time,
                _,
            ) = object_name.split("_", 5)
            return re.compile(
                rf"(.*)/{production_number}_{firmware_version}_(.*)_{extract_date}_{extract_time}_(.*)\.{target_file_type}"
            )

        prefix, object_name, file_type = filter(None, re.split(r"(.*\/)|.([a-zA-Z]*$)", file_path))
        target_file_type = __determine_target_file_type()
        paired_file_regex = (
            regex_above_X3() if object_name.startswith("CLBX-") else regex_below_X2()
        )
        bucket_object_names = S3Helper.get_object_names(prefix, bucket_name=bucket_name)
        filtered_file_path = list(filter(paired_file_regex.match, bucket_object_names))
        return filtered_file_path[0] if filtered_file_path else None
