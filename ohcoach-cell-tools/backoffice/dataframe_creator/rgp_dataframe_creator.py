from enum import Enum

import pandas as pd

from backoffice.app_component.app_callback.rgp_callback import RgpCallback
from backoffice.constants import RGP_ELEMENTS
from backoffice.dataframe_creator.common_creator import concat_df, filter_column_and_add_cell_number

# 도움말 보러 가기
# https://www.notion.so/fitogether/backoffice-726b2761368b41e588466ba130035a21#1640e4b84cfb4db69ea861ab82a06a49


class PosmodeValue(Enum):
    N = 1
    A = 0
    D = 0


def extract_splited_rgp_df(rgp: pd.DataFrame, file_name: str) -> dict:
    rgp = rgp.astype({"pos_mode": "category"})
    rgp["pos_mode"] = rgp["pos_mode"].apply(lambda x: PosmodeValue[x].value)
    rgp_set = {}
    for col in RGP_ELEMENTS:
        rgp_set[col] = filter_column_and_add_cell_number(rgp, file_name, ["datetime", col])
    graph_df_set = RgpCallback.graph_df_set
    if graph_df_set["h_acc"] is not None:
        rgp_set = concat_df(rgp_set, graph_df_set)
    return rgp_set
