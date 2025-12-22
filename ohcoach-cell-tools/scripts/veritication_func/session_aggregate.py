import numpy as np

from scripts.veritication_func.common import ACTION, COMPUTED, save_json


class SessionAggregate:
    @property
    def df(self):
        return self._df

    @df.setter
    def df(self, df):
        self._df = df

    def create_session_data_formation_aggreagte_json(
        self, detail_datetime: list[str], result_dir: str, file_name: str
    ):
        start, end = detail_datetime
        self._df = self._df[(start <= self._df["datetime"]) & (self._df["datetime"] <= end)]
        replace_str = ACTION if ACTION in file_name else COMPUTED
        file_name = file_name.replace(
            replace_str, f"{replace_str}_session_data_formation_aggregate"
        )
        if self._df.empty:
            print(f"dataframe empty , detail_datetime : {detail_datetime}")
            return
        _formation_aggregate = self.formation_aggregate
        save_json(_formation_aggregate, result_dir, file_name)

    def create_session_data_heatmap_aggreagte_json(
        self, heatmap_stadium: list[int], result_dir: str, file_name: str
    ):
        replace_str = ACTION if ACTION in file_name else COMPUTED
        _heatmap_aggregate = self.heatmap_aggregate(heatmap_stadium, replace_str)
        file_name = file_name.replace(replace_str, f"{replace_str}_session_data_heatmap_aggregate")
        save_json(_heatmap_aggregate, result_dir, file_name)

    def heatmap_aggregate(
        self, heatmap_stadium: list[int], replace_str: str
    ) -> dict[int, list[list[int]]]:
        stadium_x, stadium_y = heatmap_stadium
        grid_x, grid_y = [6, 3] if replace_str == ACTION else [96, 72]
        heatmap = [[0] * grid_y for _ in range(grid_x)]
        for row in self._df.itertuples():
            x = int((getattr(row, "loc_x") / stadium_x) * grid_x)
            y = int((getattr(row, "loc_y") / stadium_y) * grid_y)
            heatmap[x][y] += 1
        return {0: heatmap}

    @property
    def formation_aggregate(self) -> dict[str, float]:
        x = 0.0 if np.isnan(abs_x := self._df["loc_x"].mean()) else abs_x
        y = 0.0 if np.isnan(abs_y := self._df["loc_y"].mean()) else abs_y
        sesstion_aggregate = {"x": x, "y": y}
        return sesstion_aggregate
