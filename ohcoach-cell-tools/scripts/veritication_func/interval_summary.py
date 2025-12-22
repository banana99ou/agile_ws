import json
from datetime import timedelta

import pandas as pd

from scripts.veritication_func.action_aggregate import ActionAggregate
from scripts.veritication_func.common import ACTION, COMPUTED
from scripts.veritication_func.computed_aggregate import ComputedAggregate


class IntervalSummary:
    def __init__(self, computed_df: pd.DataFrame, file_path: str, basename: str):
        self.action_df = self.read_action_df(file_path, basename)
        self.action_df["datetime"] = pd.to_datetime(self.action_df["datetime"])
        self.computed_df = computed_df
        self.computed_df["datetime"] = pd.to_datetime(self.computed_df["datetime"])
        self.one_second = timedelta(milliseconds=1)

    def read_action_df(self, file_path: str, basename: str) -> pd.DataFrame:
        action_name = basename.replace(COMPUTED, ACTION)
        action_path = file_path.replace(basename, action_name)
        action_df = pd.read_csv(action_path)
        return action_df

    def create_interval_summary_json(self, result_dir, file_name):
        minute_1 = self.create_interval_summary(timedelta(minutes=1) - self.one_second)
        minute_5 = self.create_interval_summary(timedelta(minutes=5) - self.one_second)
        minute_15 = self.create_interval_summary(timedelta(minutes=15) - self.one_second)
        common_path = f"{result_dir}/{file_name}_interval_summary"
        end_path = "minute.json"
        interval_summary_path = [
            f"{common_path}_1_{end_path}",
            f"{common_path}_5_{end_path}",
            f"{common_path}_15_{end_path}",
        ]

        for path, summary in zip(interval_summary_path, [minute_1, minute_5, minute_15]):
            with open(path, "w") as outfile:
                json.dump(summary, outfile, indent=4)

    def filter_df_datetime(
        self, df: pd.DataFrame, start: timedelta, end: timedelta
    ) -> pd.DataFrame:
        filter_df = df[(start <= df["datetime"]) & (df["datetime"] <= end)]
        return filter_df

    def create_interval_summary(self, time_interval: timedelta) -> dict[int, dict]:
        cnt, end_cursor = 0, 0
        row = len(self.computed_df)
        computed_aggregate = ComputedAggregate()
        action_aggregate = ActionAggregate()
        start = self.computed_df.loc[0, "datetime"]
        end = start + time_interval
        result = {}

        while end_cursor < row:
            computed_filter_df = self.filter_df_datetime(self.computed_df, start, end)
            action_filter_df = self.filter_df_datetime(self.action_df, start, end)
            computed_aggregate.df = computed_filter_df
            action_aggregate.df = action_filter_df
            result[cnt] = {
                "time": str(computed_filter_df.iloc[0, 0]),
                COMPUTED: {**computed_aggregate.computed_aggregate},
                ACTION: {**action_aggregate.action_aggregate},
            }
            cnt += 1
            start = end
            end = start + time_interval
            end_cursor += len(computed_filter_df)
        return result
