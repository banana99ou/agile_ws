import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, State
from plotly_resampler import register_plotly_resampler

from backoffice.app_component.app_callback.common_callback import (
    create_graph_output_elements,
    create_minimize_maximize_button,
    get_minimize_maximize_button_elements,
)
from backoffice.app_component.app_callback.rbs_callback import RbsCallback
from backoffice.app_component.app_callback.rgp_callback import RgpCallback
from backoffice.app_component.app_callback.rim_callback import RimCallback
from backoffice.app_component.app_html.common_html import CommonHtml
from backoffice.app_component.app_html.rbs_html import get_rbs_html
from backoffice.app_component.app_html.rgp_html import get_rgp_html
from backoffice.app_component.app_html.rim_html import get_rim_html
from backoffice.constants import RBS_ELEMENTS, RGP_ELEMENTS, RIM_ELEMENTS
from backoffice.dataframe_creator.datetime_creator import get_now_datetime
from backoffice.ftg_management import (
    convert_ftg_rgp_rim_rbs_and_return_message,
    get_ftg_list_exclude_bucket_name,
    get_ftg_list_include_bucket_name,
    ohcoach_data_s3_team_list,
)

# 도움말 보러 가기
# https://www.notion.so/fitogether/backoffice-ftg-726b2761368b41e588466ba130035a21#b451297082334d3b8829ca14156077f2

register_plotly_resampler(mode="auto")
# 현재 시간
now = get_now_datetime()

# s3 버킷 ohcoach-data 하위 팀 리스트 가져오기
team_list = ohcoach_data_s3_team_list()
ftg_parse_message = {"data": [], "columns": ["ftg_file_name", "index", "start", "end", "error"]}

app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME])

# html 불러오기
rgp_html = get_rgp_html(RGP_ELEMENTS)
rim_html = get_rim_html(RIM_ELEMENTS)
rbs_html = get_rbs_html(RBS_ELEMENTS)
ftg_file_html = CommonHtml.create_ftg_file_select_html(now, team_list)
datatable_html = CommonHtml.create_datatable_html(ftg_parse_message)
tab_html = CommonHtml.create_tab_html(rgp_html, rim_html, rbs_html)
app.layout = CommonHtml.create_app_layout_html(ftg_file_html, tab_html, datatable_html)


@app.callback(
    [Output("ftg-file-dropdown", "options"), Output("ftg-file-dropdown", "placeholder")],
    [Input("team-dropdown", "value"), Input("ftg-datetime-picker", "date")],
)
def update_ftg_list(idf_team, select_datetime):
    if idf_team is not None:
        ftg_list_include_bucket_name = get_ftg_list_include_bucket_name(idf_team, select_datetime)
        ftg_list_exclude_bucket_name = get_ftg_list_exclude_bucket_name(
            idf_team, ftg_list_include_bucket_name
        )
        if ftg_list_include_bucket_name:
            dropdown_options = [
                {"label": exclude, "value": include}
                for exclude, include in zip(
                    ftg_list_exclude_bucket_name, ftg_list_include_bucket_name
                )
            ]
            return dropdown_options, "ftg 파일을 선택하세요."
        return [], "ftg 파일이 존재하지 않습니다."
    return [], "팀을 선택하세요."


# 2. 선택한 ftg 파일 rgp, rim, rbs 생성하여 그래프에 그리기
rgp_graph_output_elements = create_graph_output_elements("rgp", RGP_ELEMENTS)
rim_graph_output_elements = create_graph_output_elements("rim", RIM_ELEMENTS)
rbs_graph_output_elements = create_graph_output_elements("rbs", RBS_ELEMENTS)


@app.callback(
    [
        *rgp_graph_output_elements,
        *rim_graph_output_elements,
        *rbs_graph_output_elements,
        Output("ftg-parse-message-datatable", "data"),
    ],
    [Input("ftg-file-dropdown", "value")],
    prevent_initial_call=True,
)
def create_graph_datatable(ftg_file):
    select_ftg_file = [ftg_file_set["ftg_file_name"] for ftg_file_set in ftg_parse_message["data"]]
    if ftg_file is not None and ftg_file not in select_ftg_file:
        ftg_parse_message["data"] += convert_ftg_rgp_rim_rbs_and_return_message(
            ftg_file, ftg_parse_message
        )
        rgp_fig = RgpCallback.update_rgp_graph(RGP_ELEMENTS)
        rim_fig = RimCallback.update_rim_graph(RIM_ELEMENTS)
        rbs_fig = RbsCallback.update_rbs_graph(RBS_ELEMENTS)

        result_data = [
            *rgp_fig,
            *rim_fig,
            *rbs_fig,
            ftg_parse_message["data"],
        ]
        print("파일 읽기 완료")
        return result_data


# 그래프 최대화 최소화 버튼
(
    min_max_output_elements,
    min_max_input_elements,
    min_max_state_elements,
) = get_minimize_maximize_button_elements(
    ["rgp", "rim", "rbs"], [RGP_ELEMENTS, RIM_ELEMENTS, RBS_ELEMENTS]
)

for min_max_output_element, min_max_input_element, min_max_state_element in zip(
    min_max_output_elements, min_max_input_elements, min_max_state_elements
):
    update_min_max_button = create_minimize_maximize_button(min_max_output_element)
    app.callback(
        [
            Output(min_max_output_element[0], "className"),
            Output(min_max_output_element[1], "className"),
            Output(min_max_output_element[2], "className"),
        ],
        [
            Input(min_max_input_element, "n_clicks"),
            State(min_max_state_element, "className"),
        ],
    )(update_min_max_button)

if __name__ == "__main__":
    app.run_server(debug=True)
