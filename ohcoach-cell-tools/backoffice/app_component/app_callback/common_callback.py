from typing import List, Tuple

import pandas as pd
import plotly.express as px
from dash import Output

from backoffice.app_component.html_id import (
    get_graph_div_id,
    get_graph_id,
    get_maximize_a_id,
    get_maximize_i_id,
)
from backoffice.layout_option import AXES_OPTION, LAYOUT_OPTION

# 도움말 보러 가기
# https://www.notion.so/fitogether/backoffice-plotly-726b2761368b41e588466ba130035a21#c2a72af0200b4451b3b48a5baa83b0b3


def create_graph_output_elements(df_type: str, names: List[str]) -> Tuple[list, list]:
    output_elements = []
    for name in names:
        graph_id = get_graph_id(df_type, name)
        output_elements.append(Output(graph_id, "figure"))
    return output_elements


def get_minimize_maximize_button_elements(df_types: List[str], names_list: List[str]):
    min_max_output_elements = []
    min_max_input_elements = []
    min_max_state_elements = []
    for df_type, names in zip(df_types, names_list):
        output_elements, input_elements, state_elements = create_minimize_maximize_button_elements(
            df_type, names
        )
        min_max_output_elements += output_elements
        min_max_input_elements += input_elements
        min_max_state_elements += state_elements
    return min_max_output_elements, min_max_input_elements, min_max_state_elements


def create_minimize_maximize_button_elements(
    df_type: str, names: List[str]
) -> Tuple[list, list, list]:
    output_elements = []
    input_elements = []
    state_elements = []
    for name in names:
        output_elements.append(
            [
                get_graph_div_id([df_type, name]),
                get_graph_id(df_type, name),
                get_maximize_i_id(df_type, name),
            ]
        )
        input_elements.append(get_maximize_a_id(df_type, name))
        state_elements.append(get_maximize_i_id(df_type, name))
    return output_elements, input_elements, state_elements


def create_minimize_maximize_button(output):
    graph_div_size_class_name = {
        "maximize": ["each-div panel-fullscreen", "", "fa-sharp fa-solid fa-compress maximize"],
        "minimize": ["each-div", "minize_graph", "fa-sharp fa-solid fa-expand minimize"],
    }

    def callback(_, min_max_state):
        if "minimize" in min_max_state:
            return graph_div_size_class_name["maximize"]
        return graph_div_size_class_name["minimize"]

    return callback


def update_graph(df: pd.DataFrame, y_axes: str) -> px.line:
    fig = px.line(df, x="datetime", y=y_axes, color="cell_number", render_mode="webg1")
    fig.update_layout(LAYOUT_OPTION)
    fig.update_xaxes(AXES_OPTION)
    fig.update_yaxes(AXES_OPTION)
    return fig
