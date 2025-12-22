from datetime import datetime

from pytz import timezone

from ohcoach_cell_tools.common.logger import Logger
from ohcoach_cell_tools.constants import HEADER_RGP
from ohcoach_cell_tools.ftg_parser.converters.ftg_to_gp_converter import GpConverter
from ohcoach_cell_tools.ftg_parser.converters.ftg_to_im_converter import ImConverter
from ohcoach_cell_tools.ftg_parser.ftg_parser import FtgParser
from ohcoach_cell_tools.publishers.backoffice_ftg_parser_publisher import (
    BackOfficeFtgParserPublisher,
)
from scripts.parse import add_time_gap_error_info

logger = Logger("lambda_backoffice_ftg_parser")
timestamp = datetime.now(timezone("Asia/Seoul")).strftime("%Y%m%d%H%M%S")


def run(bucket_name, file_key):
    contents = BackOfficeFtgParserPublisher.fetch_cell_data_from_s3(bucket_name, file_key)
    cumulative_parsing_errors = {}

    cumulative_gp_contents = bytearray()
    cumulative_im_contents = bytearray(
        b"100,-0.013672,0.019470,-0.078003,-1.725191,2.824427,-0.946565,1.191406,1.195312,1.156250"
    )

    for i, (start, rgp, rim, rbs, end, parsing_errors) in enumerate(FtgParser.parse(contents)):
        index = i + 1

        logger.info(f"[FTG-Lambda] index: {index} / start: {start} / end: {end}")

        if rgp.empty or rim.empty or rbs.empty:
            cumulative_parsing_errors[index] = [
                f"[FTG-Lambda] Empty dataframe(s), index: {index}, start: {start}"
            ]
            continue
        add_time_gap_error_info(rgp, rim, rbs)

        BackOfficeFtgParserPublisher.push_to_s3(
            bucket_name, file_key, index, category="rgp", df=rgp
        )
        BackOfficeFtgParserPublisher.push_to_s3(
            bucket_name, file_key, index, category="rim", df=rim
        )

        BackOfficeFtgParserPublisher.push_to_s3(
            bucket_name, file_key, index, category="rbs", df=rbs
        )

        if start is None:
            parsing_errors.append("[FTG-Lambda] Error: start is None")

        cumulative_gp_contents += GpConverter.encode_to_gp_format(rgp[HEADER_RGP])
        cumulative_im_contents += ImConverter.encode_to_im_format(rim)

        cumulative_parsing_errors[index] = parsing_errors.copy()

        del rgp, rim, rbs

    BackOfficeFtgParserPublisher.push_to_s3(
        bucket_name, file_key, extension="gp", byt=cumulative_gp_contents
    )

    BackOfficeFtgParserPublisher.push_to_s3(
        bucket_name, file_key, extension="im", byt=cumulative_im_contents
    )

    return cumulative_parsing_errors


def lambda_handler(event, context):
    file_obj = event["Records"][0]

    bucket_name = file_obj["s3"]["bucket"]["name"]
    file_name = file_obj["s3"]["object"]["key"]

    logger.info(f"[FTG-Lambda] Start - bucket_name: {bucket_name}, file_name: {file_name}")

    try:
        parsing_errors = run(bucket_name, file_name)

        logger.info(f"[FTG-Lambda] Parsing Errors: {parsing_errors}")
    except Exception as e:
        logger.exception(f"[FTG-Lmabda] File name: {file_name} | Exception: {e}")
    else:
        logger.info(f"[FTG-Lambda] Parsing Done: {file_name}")

        BackOfficeFtgParserPublisher.push_to_s3(
            bucket_name,
            file_name,
            extension="log",
            log_file=logger.log_messages,
            timestamp_log=timestamp,
        )

        return {"statusCode": 200}
