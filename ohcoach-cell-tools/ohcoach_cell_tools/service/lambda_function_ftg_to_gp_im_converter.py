import json

from ohcoach_cell_tools.common.logger import Logger
from ohcoach_cell_tools.common.web1_api_helper import Web1ApiHelper
from ohcoach_cell_tools.constants import HEADER_RGP
from ohcoach_cell_tools.ftg_parser.converters.ftg_to_gp_converter import GpConverter
from ohcoach_cell_tools.ftg_parser.converters.ftg_to_im_converter import ImConverter
from ohcoach_cell_tools.ftg_parser.ftg_parser import FtgParser
from ohcoach_cell_tools.publishers.gp_im_publisher import GpImPublisher

TITLE = "[FTG2GPIM-Lambda]"
logger = Logger("lambda_ftg_to_gp_im_converter")


def run(bucket_name, file_key):
    contents = GpImPublisher.fetch_cell_data_from_s3(bucket_name, file_key)
    cumulative_parsing_errors = {}

    cumulative_gp_contents = bytearray()
    cumulative_im_contents = bytearray(
        b"100,-0.013672,0.019470,-0.078003,-1.725191,2.824427,-0.946565,1.191406,1.195312,1.156250"
    )

    for i, (start, rgp, rim, rbs, end, parsing_errors) in enumerate(FtgParser.parse(contents)):
        index = i + 1

        logger.info(f"{TITLE} index: {index} / start: {start} / end: {end}")

        if rgp.empty or rim.empty or rbs.empty:
            cumulative_parsing_errors[index] = [
                f"{TITLE} Empty dataframe(s), index: {index}, start: {start}"
            ]
            continue

        cumulative_gp_contents += GpConverter.encode_to_gp_format(rgp[HEADER_RGP])
        cumulative_im_contents += ImConverter.encode_to_im_format(rim)

        cumulative_parsing_errors[index] = parsing_errors.copy()

        del rgp, rim, rbs

    gp_key = GpImPublisher.push_converted_data_to_s3(
        cumulative_gp_contents,
        bucket_name,
        file_key,
        "gp",
    )

    im_key = GpImPublisher.push_converted_data_to_s3(
        cumulative_im_contents,
        bucket_name,
        file_key,
        "im",
    )

    result = Web1ApiHelper.update_db_original_data_from_ftg(file_key, gp_key, im_key)

    logger.info(f"{TITLE} gp: {gp_key} / im: {im_key} published and register result {result}")

    return cumulative_parsing_errors


def lambda_handler(event, _):
    try:
        file_obj = event["Records"][0]

        bucket_name = file_obj["s3"]["bucket"]["name"]
        file_name = file_obj["s3"]["object"]["key"]

        logger.info(f"{TITLE} Start - bucket_name: {bucket_name}, file_name: {file_name}")

        parsing_errors = run(bucket_name, file_name)

        logger.info(f"{TITLE} Parsing Errors: {parsing_errors}")
    except Exception as e:
        logger.info(f"{TITLE} Exception: {e}")

        raise e
    else:
        logger.info(f"{TITLE} Parsing & Conversion Done: {file_name}")

        return {
            "statusCode": 200,
            "body": json.dumps("Done"),
        }
