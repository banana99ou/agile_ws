import os
from typing import List, Tuple

from backoffice.app_component.app_callback.rbs_callback import RbsCallback
from backoffice.app_component.app_callback.rgp_callback import RgpCallback
from backoffice.app_component.app_callback.rim_callback import RimCallback
from backoffice.connections import OhcoachDataConnection
from backoffice.dataframe_creator.datetime_creator import extract_year_month_day_from_datetime
from backoffice.dataframe_creator.rbs_dataframe_creator import extract_splited_rbs_df
from backoffice.dataframe_creator.rgp_dataframe_creator import extract_splited_rgp_df
from backoffice.dataframe_creator.rim_dataframe_creator import extract_splited_rim_df
from backoffice.parse import run
from ohcoach_cell_tools.common.aws_s3_helper import S3Helper

# 도움말 보러 가기
# https://www.notion.so/fitogether/backoffice-ftg-726b2761368b41e588466ba130035a21#d4e69adbb87242efbd4f6575c1feb14b


ENV_S3_BUCKET = os.getenv("ENV_S3_BUCKET")
ohcoach_team = OhcoachDataConnection()


def ohcoach_data_s3_team_list() -> list[dict[str, str]]:
    team = ohcoach_team.team
    return team


def get_ftg_list_include_bucket_name(idf_team: str, _select_dateime: str) -> List[str]:
    select_datetime = extract_year_month_day_from_datetime(_select_dateime)
    prefix = f"original/team_{idf_team}/{select_datetime['year']}/{select_datetime['month']}/{select_datetime['day']}/"
    file_list_include_bucket_name = S3Helper.get_object_names(prefix, ENV_S3_BUCKET)
    ftg_list_include_bucket_name = [
        file for file in file_list_include_bucket_name if file.endswith(".ftg")
    ]
    return ftg_list_include_bucket_name


def get_ftg_list_exclude_bucket_name(
    idf_team: str, ftg_list_include_bucket_name: List[str]
) -> List[str]:
    player_info = ohcoach_team.get_cell_of_player(idf_team)
    ftg_list_exclude_bucket_name = []
    for file in ftg_list_include_bucket_name:
        ftg_name = file.rsplit("/")[-1]
        cell_info = ftg_name.split("_", 1)[0]
        try:
            ftg_list_exclude_bucket_name.append(f"{ftg_name} ({player_info[cell_info]})")
        except Exception:
            ftg_list_exclude_bucket_name.append(ftg_name)
    return ftg_list_exclude_bucket_name


def convert_ftg_rgp_rim_rbs_and_return_message(
    ftg_file: str, ftg_parse_message: dict
) -> Tuple[dict, list]:
    ftg_file_name = ftg_file.split("/")[-1]
    ftg_data = S3Helper.read_data(obj_name=ftg_file, bucket_name=ENV_S3_BUCKET)
    rgp, rim, rbs, message = run(ftg_data)
    RgpCallback.graph_df_set = extract_splited_rgp_df(rgp, ftg_file_name)
    RimCallback.graph_df_set = extract_splited_rim_df(rim, ftg_file_name)
    RbsCallback.graph_df_set = extract_splited_rbs_df(rbs, ftg_file_name)
    ftg_parse_message = [{"ftg_file_name": ftg_file_name, **msg} for msg in message]
    return ftg_parse_message
