from typing import List

from dash import html

from backoffice.app_component.app_html.common_html import CommonHtml


def get_rim_html(elements_id: List[str]) -> html.Div:
    """
    컬럼마다 생성한 그래프를 하나의 div에 담아서 리턴해주는 함수
    """
    graph_list = CommonHtml.get_graph_html_list("rim", elements_id)
    _html = html.Div(
        [
            html.Div(
                [*graph_list],
                className="rim-graph-div",
            ),
        ],
        className="graph-parent-div",
    )
    return _html
