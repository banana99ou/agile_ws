import pandas as pd

# 도움말 보러 가기
# https://www.notion.so/fitogether/backoffice-plotly-726b2761368b41e588466ba130035a21#4fe97cf68fbd445e9f1d0f90059715d8


def filter_column_and_add_cell_number(
    df: pd.DataFrame, file_name: str, columns: list
) -> pd.DataFrame:
    df_copy = df[columns].copy()
    cell_number = file_name.split("-")[2].split("_")[0]
    df_copy["cell_number"] = cell_number
    return df_copy


def concat_df(df_set: dict, _graph_df_set: dict) -> dict:
    df_set_copy = df_set
    for prev, curr, key in zip(_graph_df_set.values(), df_set_copy.values(), df_set_copy.keys()):
        con_df = pd.concat([prev, curr])
        con_df.reset_index(drop=True, inplace=True)
        df_set_copy[key] = con_df

    return df_set_copy


def get_cell_number_list(df_set: dict, col: str) -> list:
    cell_number_list = sorted(set(df_set[col]["cell_number"]))
    return cell_number_list
