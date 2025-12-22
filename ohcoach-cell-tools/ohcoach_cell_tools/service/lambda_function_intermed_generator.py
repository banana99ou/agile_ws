from typing import Optional, Tuple

from ohcoach_cell_tools.common.aws_s3_helper import S3Helper
from ohcoach_cell_tools.common.logger import Logger
from ohcoach_cell_tools.gp_im_parser.generators.intermed_generator import IntermedGenerator
from ohcoach_cell_tools.gp_im_parser.utils.cell_info_utils import CellInfo

logger = Logger("lambda_intermed_generator")


def lambda_handler(event, context):
    if event:
        file_obj = event["Records"][0]
        bucket_name = file_obj["s3"]["bucket"]["name"]
        file_path = str(file_obj["s3"]["object"]["key"])

        logger.info(f"[INTERMED] original_file_path : {file_path} - Start")

        cell_info = CellInfo(file_path=file_path)

        gp_file_path, im_file_path = __get_gp_im_file_path(file_path, bucket_name)

        if not (gp_file_path and im_file_path):
            logger.info(
                f"[INTERMED] original_file_path : {file_path} - "
                + f"gp_file_path : {gp_file_path} - im_file_path : {im_file_path}"
            )
            return {"statusCode": 404}

        try:
            intermed_generator = IntermedGenerator(
                cell_info=cell_info,
                gp_data=S3Helper.read_data(obj_name=gp_file_path, bucket_name=bucket_name),
                im_data=S3Helper.read_data(obj_name=im_file_path, bucket_name=bucket_name),
            )
            intermed_generator.run()

            rim_data_list = intermed_generator.rim_data_list
            __write_data_to_s3(rim_data_list, im_file_path, bucket_name, "im")

            rgp_data_list = intermed_generator.rgp_data_list
            __write_data_to_s3(rgp_data_list, gp_file_path, bucket_name, "gp")

        except Exception as e:
            logger.error(f"[INTERMED] original_file_path : {file_path} - Exception : {e}")
            return {"statusCode": 422}

        return {"statusCode": 200}


def __write_data_to_s3(data_list: list, file_path: str, bucket_name: str, extension: str):
    for data in data_list:
        intermed_file_path = file_path.replace("original", "intermed").replace(
            f".{extension}", data.postfix
        )
        S3Helper.write_data(
            obj_name=intermed_file_path, body=data.df.to_csv(), bucket_name=bucket_name
        )
        logger.info(
            f"[INTERMED] original_file_path : {file_path} - intermed_file_path : {intermed_file_path}"
        )


def __get_gp_im_file_path(file_path: str, bucket_name: str) -> Tuple[Optional[str], Optional[str]]:
    paired_file_path = S3Helper.find_paired_file(file_path=file_path, bucket_name=bucket_name)

    if file_path.endswith(".gp"):
        return file_path, paired_file_path

    return paired_file_path, file_path
