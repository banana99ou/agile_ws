import pandas as pd

from backoffice.app_component.app_callback.rim_callback import RimCallback
from backoffice.constants import RIM_ELEMENTS
from backoffice.dataframe_creator.common_creator import concat_df, filter_column_and_add_cell_number

# 도움말 보러 가기
# https://www.notion.so/fitogether/backoffice-ftg-726b2761368b41e588466ba130035a21#b8f4aad4444a4ad49557de4d2cbad02a


def extract_splited_rim_df(rim: pd.DataFrame, file_name: str) -> dict:
    rim_set = {}
    for col in RIM_ELEMENTS:
        rim_set[col] = filter_column_and_add_cell_number(rim, file_name, ["datetime", col])
    graph_df_set = RimCallback.graph_df_set
    if graph_df_set["acc_x"] is not None:
        rim_set = concat_df(rim_set, graph_df_set)
    return rim_set
