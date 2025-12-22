from typing import Dict, Optional

from backoffice.app_component.app_callback.common_callback import update_graph
from backoffice.constants import RBS_ELEMENTS

# 도움말 보러 가기
# https://www.notion.so/fitogether/backoffice-ftg-726b2761368b41e588466ba130035a21#76606a3345f44da98452c44fd00cddb8


class RbsCallback:
    graph_df_set: Dict[str, Optional[dict]] = {col: None for col in RBS_ELEMENTS}

    @classmethod
    def update_rbs_graph(cls, graph_elements: list) -> list:
        fig = []
        for col in graph_elements:
            _fig = update_graph(
                df=cls.graph_df_set[col],
                y_axes=col,
            )
            fig.append(_fig)
        return fig
