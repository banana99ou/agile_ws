import json

from ohcoach_cell_tools.common.logger import Logger
from ohcoach_cell_tools.constants import HEADER_RBS, HEADER_RGP, HEADER_RIM
from ohcoach_cell_tools.ftg_parser.ftg_parser import FtgParser
from ohcoach_cell_tools.ftg_parser.managers.bs_message_manager import BsMessageManager
from ohcoach_cell_tools.ftg_parser.utils.ftg_message_utils import (
    get_datetime_third_decimal_place,
    get_filtered_dataframe,
)
from ohcoach_cell_tools.publishers.intermed_publisher import IntermedPublisher
from ohcoach_cell_tools.publishers.raw_data_publisher import RawDataPublisher

logger = Logger("lambda_intermed_generator_ftg")


def run(bucket_name, file_path):
    contents = IntermedPublisher.fetch_cell_data_from_s3(bucket_name, file_path)
    cumulative_parsing_errors = {}

    for i, (start, rgp, rim, rbs, end, parsing_errors) in enumerate(FtgParser.parse(contents)):
        index = i + 1

        logger.info(f"[INTERMED-FTG] index : {index} / start : {start} / end : {end}")

        if rgp.empty or rim.empty or rbs.empty:
            cumulative_parsing_errors[index] = [
                f"[INTERMED-FTG] Empty dataframe(s), index : {index}, start : {start}"
            ]
            continue

        if bucket_name == "backoffice-cell-data":
            try:
                IntermedPublisher.push_dataframe_to_s3_backoffice(
                    rgp,
                    bucket_name,
                    file_path,
                    index,
                    "rgp",
                )
                IntermedPublisher.push_dataframe_to_s3_backoffice(
                    rgp,
                    bucket_name,
                    file_path,
                    index,
                    "rim",
                )
                IntermedPublisher.push_dataframe_to_s3_backoffice(
                    rbs,
                    bucket_name,
                    file_path,
                    index,
                    "rbs",
                )
            except Exception as e:
                logger.error(f"[INTERMED-FTG] ftg_file_path : {file_path} - Exception : {e}")

        else:
            try:
                rim_df = get_filtered_dataframe(df=rim)
                rim_file_path = IntermedPublisher.push_dataframe_to_s3(
                    get_datetime_third_decimal_place(df=rim_df),
                    bucket_name,
                    file_path,
                    index,
                    HEADER_RIM,
                    "rim",
                )

                rbs_file_path = None
                if BsMessageManager.check_ble_connected(rbs):
                    rbs_df = get_filtered_dataframe(df=rbs)
                    rbs_file_path = IntermedPublisher.push_dataframe_to_s3(
                        get_datetime_third_decimal_place(df=rbs_df),
                        bucket_name,
                        file_path,
                        index,
                        HEADER_RBS,
                        "rbs",
                    )
                else:
                    logger.info("[INTERMED-FTG] BLE not connected : no RBS")

                raw_data_publisher = RawDataPublisher(
                    rgp_df=rgp,
                    rim_df=rim,
                    rbs_df=rbs,
                    original_file_path=file_path,
                    index=index,
                )
                raw_data_file_path = raw_data_publisher.push_dataframe_to_s3(
                    bucket_name=bucket_name
                )

                rgp_df = get_filtered_dataframe(df=rgp)
                rgp_file_path = IntermedPublisher.push_dataframe_to_s3(
                    get_datetime_third_decimal_place(df=rgp_df),
                    bucket_name,
                    file_path,
                    index,
                    HEADER_RGP,
                    "rgp",
                )
            except Exception as e:
                logger.error(f"[INTERMED-FTG] ftg_file_path : {file_path} - Exception : {e}")
            else:
                logger.info(
                    f"[INTERMED-FTG] ftg_file_path : {file_path} - rgp_file_path : {rgp_file_path}"
                    + f" - rim_file_path : {rim_file_path} - rbs_file_path : {rbs_file_path}"
                    + f" - raw_data_file_path : {raw_data_file_path}"
                )

        cumulative_parsing_errors[index] = parsing_errors.copy()

        del rgp, rim, rbs

    return cumulative_parsing_errors


def lambda_handler(event, context):
    file_obj = event["Records"][0]

    bucket_name = file_obj["s3"]["bucket"]["name"]
    file_name = file_obj["s3"]["object"]["key"]

    try:
        parsing_errors = run(bucket_name, file_name)

        logger.info(f"[INTERMED-FTG] Parsing Errors : {parsing_errors}")
    except Exception as e:
        logger.exception(f"[INTERMED-FTG] ftg_file_path : {file_name} - Exception: {e}")
    else:
        logger.info(f"[INTERMED-FTG] ftg_file_path : {file_name} - Done")

    return {"statusCode": 200, "body": json.dumps("Done")}
