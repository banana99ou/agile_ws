# 도움말 보러 가기
# https://www.notion.so/fitogether/backoffice-plotly-726b2761368b41e588466ba130035a21#4b05f20719894315a27c7d2899c3549a


def get_graph_id(df_type: str, name: str) -> str:
    return f"{df_type}_{name}_graph"


def get_maximize_a_id(df_type: str, name: str) -> str:
    return f"{df_type}_{name}_maximize_a"


def get_maximize_i_id(df_type: str, name: str) -> str:
    return f"{df_type}_{name}_maximize_i"


def get_graph_div_id(names: list) -> str:
    return f"{names[0]}_div" if len(names) == 1 else f"{names[0]}_{names[1]}_graph_div"
