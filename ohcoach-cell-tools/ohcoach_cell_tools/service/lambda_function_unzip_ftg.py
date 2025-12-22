import gzip
from io import BytesIO

from ohcoach_cell_tools.common.aws_s3_helper import S3Helper
from ohcoach_cell_tools.common.logger import Logger

logger = Logger("lambda_unzip_ftg")


def run(bucket_name: str, file_path: str):
    ftg_file_path = f"original/{'/'.join(file_path.split('/')[1:])}".replace(".gz", "")
    zip_data = BytesIO(S3Helper.read_data(obj_name=file_path))

    S3Helper.write_data(
        obj_name=ftg_file_path,
        body=gzip.GzipFile(fileobj=zip_data, mode="r"),
        bucket_name=bucket_name,
    )


def lambda_handler(event, context):
    file_obj = event["Records"][0]
    bucket_name = file_obj["s3"]["bucket"]["name"]
    file_name = file_obj["s3"]["object"]["key"]

    try:
        run(bucket_name, file_name)
    except Exception as e:
        logger.error(f"[UNZIP-FTG] file_path : {file_name} - Exception : {e}")
        return {"statusCode": 422}
    else:
        logger.info(f"[UNZIP-FTG] file_path : {file_name} - Success")

    return {"statusCode": 200}
