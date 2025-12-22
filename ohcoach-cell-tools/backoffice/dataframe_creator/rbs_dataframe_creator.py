import pandas as pd

from backoffice.app_component.app_callback.rbs_callback import RbsCallback
from backoffice.constants import RBS_ELEMENTS
from backoffice.dataframe_creator.common_creator import concat_df, filter_column_and_add_cell_number


def extract_splited_rbs_df(rbs: pd.DataFrame, file_name: str) -> dict:
    rbs_set = {}
    for col in RBS_ELEMENTS:
        rbs_set[col] = filter_column_and_add_cell_number(rbs, file_name, ["datetime", col])
    graph_df_set = RbsCallback.graph_df_set
    if graph_df_set["hr"] is not None:
        rbs_set = concat_df(rbs_set, graph_df_set)
    return rbs_set
