from datetime import date
from typing import List

import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html

from backoffice.app_component.html_id import (
    get_graph_div_id,
    get_graph_id,
    get_maximize_a_id,
    get_maximize_i_id,
)

# 도움말 보러 가기
# https://www.notion.so/fitogether/backoffice-plotly-726b2761368b41e588466ba130035a21#ed87b6074ecd41819fc5e8d02d21c9dc


class CommonHtml:
    @staticmethod
    def create_app_layout_html(
        ftg_file_html: html.Div, tag_html: dcc.Tab, table_html: html.Div
    ) -> dbc.Container:
        _container = dbc.Container(
            [html.H1("ftg 파일 그래프 보기", id="ftg-file-title"), ftg_file_html, tag_html, table_html]
        )
        return _container

    @staticmethod
    def create_ftg_file_select_html(now: list, team_list: list) -> html.Div:
        _html = html.Div(
            [
                dcc.DatePickerSingle(
                    id="ftg-datetime-picker",
                    min_date_allowed=date(2015, 1, 1),
                    max_date_allowed=date(2100, 12, 31),
                    initial_visible_month=date(*now),
                    date=date(*now),
                    display_format="YYYY/MM/DD",
                    placeholder="YYYY/MM/DD",
                ),
                dcc.Dropdown(
                    team_list, None, id="team-dropdown", placeholder="team 선택하기", optionHeight=48
                ),
                html.Div(id="team-output"),
                dcc.Dropdown(id="ftg-file-dropdown", optionHeight=60),
                html.Div(id="ftg-file-output"),
            ],
            className="ftg-select-div",
        )
        return _html

    @classmethod
    def create_graph_html(cls, h3_text: str, graph_id: str) -> html.Div:
        min_max_button_html = cls.create_min_max_button_html(graph_id)
        _html = html.Div(
            [
                html.Div(
                    [
                        html.H5(h3_text),
                        min_max_button_html,
                    ],
                    className="graph-header",
                ),
                dcc.Graph(
                    id=graph_id,
                    config={"scrollZoom": True, "displaylogo": False},
                    figure={"layout": {"plot_bgcolor": "rgba(0,0,0,0)"}},
                ),
            ],
            className="each-div",
            id=get_graph_div_id([graph_id]),
        )
        return _html

    @classmethod
    def get_graph_html_list(cls, df_type: str, names: List[str]) -> List[html.Div]:
        graph_list = [
            cls.create_graph_html(
                h3_text=name,
                graph_id=get_graph_id(df_type, name),
            )
            for name in names
        ]
        return graph_list

    @staticmethod
    def create_dataframe_each_tab_html(label: str, value: str, children: list) -> dcc.Tab:
        children_tab = dcc.Tab(
            label=label,
            value=value,
            className="custom-tab",
            selected_className="custom-tab--selected",
            children=children,
        )
        return children_tab

    @classmethod
    def create_tab_html(cls, rgp_html: html, rim_html: html, rbs_html: html) -> dcc.Tabs:
        tab = dcc.Tabs(
            id="tabs-with-classes",
            value="rgp",
            parent_className="custom-tabs",
            className="custom-tabs-container",
            children=[
                cls.create_dataframe_each_tab_html("rgp", "rgp", rgp_html),
                cls.create_dataframe_each_tab_html("rim", "rim", rim_html),
                cls.create_dataframe_each_tab_html("rbs", "rbs", rbs_html),
            ],
        )
        return tab

    @staticmethod
    def create_datatable_html(ftg_parse_message: dict) -> html.Div:
        table = dash_table.DataTable(
            [{"ftg_file_name": "", "index": "", "start": "", "end": "", "error": ""}],
            [{"name": i, "id": i} for i in ftg_parse_message["columns"]],
            id="ftg-parse-message-datatable",
            style_data={
                "whiteSpace": "normal",
                "height": "auto",
            },
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "left", "padding": "5px"},
            style_cell_conditional=[
                {"if": {"column_id": ["ftg_file_name", "index"]}, "textAlign": "center"}
            ],
        )
        _html = html.Div(
            [html.Div([html.H5("ftg 파싱 메시지"), table], className="each-div")],
            className="graph-parent-div mb-5",
        )

        return _html

    @staticmethod
    def create_min_max_button_html(graph_id: str) -> html.A:
        df_type, name = graph_id.split("_graph")[0].split("_", maxsplit=1)
        max_min_html = html.A(
            [html.I(className="fa-sharp fa-solid fa-expand", id=get_maximize_i_id(df_type, name))],
            id=get_maximize_a_id(df_type, name),
            href="#",
            className="maximize-icon-a",
        )
        return max_min_html
