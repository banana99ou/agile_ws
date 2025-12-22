from typing import Union

import numpy as np
import pandas as pd

from scripts.veritication_func.common import save_json


class ActionAggregate:
    @property
    def df(self):
        return self._df

    @df.setter
    def df(self, df):
        self._df = df

    def create_action_aggreagte_json(self, result_dir: str, file_name: str):
        action_aggregate = self.action_aggregate
        save_json(action_aggregate, result_dir, file_name)

    def create_action_data_detail_aggreagte_json(
        self, detail_datetime: str, result_dir: str, file_name: str
    ):
        self._df = self._df[self._df["initial_time"] == detail_datetime]
        file_name = file_name.replace("action", "action_data_detail")
        if self._df.empty:
            print(f"dataframe empty , detail_datetime : {detail_datetime}")
            return
        self.create_action_aggreagte_json(result_dir, file_name)

    @property
    def distance(self) -> float:
        return self._df["distance"].sum()

    @property
    def max_speed(self) -> float:
        return 0.0 if np.isnan(_max_speed := self._df["speed"].max()) else _max_speed

    @property
    def max_acceleration(self) -> Union[int, float]:
        _max = self._df["accel"].max()
        return max(0, _max)

    @property
    def max_deceleration(self) -> Union[int, float]:
        _min = self._df["accel"].min() * -1
        return max(0, _min)

    @property
    def power(self) -> float:
        power = self._df["power"].abs()
        return power.sum()

    @property
    def max_power(self) -> float:
        power = self._df["power"].abs()
        return 0.0 if np.isnan(_power := power.max()) else _power

    def type_filter(self, type_str) -> pd.DataFrame:
        filter_df = self._df[self._df["type"] == type_str]
        return filter_df

    @property
    def sprint_count(self) -> int:
        return len(self.type_filter("S"))

    @property
    def hsr_count(self) -> int:
        return len(self.type_filter("H"))

    @property
    def acceleration_count(self) -> int:
        return len(self.type_filter("A"))

    @property
    def deceleration_count(self) -> int:
        return len(self.type_filter("D"))

    @property
    def sprint_distance(self) -> float:
        sprint = self.type_filter("S")
        return sprint["distance"].sum()

    @property
    def hsr_distance(self) -> float:
        hsr = self.type_filter("H")
        return hsr["distance"].sum()

    @property
    def acceleration_distance(self) -> float:
        acceleration = self.type_filter("A")
        return acceleration["distance"].sum()

    @property
    def deceleration_distance(self) -> float:
        dcceleration = self.type_filter("D")
        return dcceleration["distance"].sum()

    @property
    def min_sprint_distance(self) -> float:
        sprint = self.type_filter("S")
        return 0.0 if np.isnan(_sprint := sprint["distance"].min()) else _sprint

    @property
    def max_sprint_distance(self) -> float:
        sprint = self.type_filter("S")
        return 0.0 if np.isnan(_sprint := sprint["distance"].max()) else _sprint

    @property
    def avg_sprint_distance(self) -> float:
        sprint = self.type_filter("S")
        return 0.0 if np.isnan(_sprint := sprint["distance"].mean()) else _sprint

    @property
    def max_sprint_power(self) -> float:
        sprint = self.type_filter("S")
        return 0.0 if np.isnan(_sprint := sprint["power"].abs().max()) else _sprint

    @property
    def max_hsr_power(self) -> float:
        hsr = self.type_filter("H")
        return 0.0 if np.isnan(_hsr := hsr["power"].abs().max()) else _hsr

    @property
    def max_acceleration_power(self) -> float:
        acceleration = self.type_filter("A")
        return 0.0 if np.isnan(_acc := acceleration["power"].abs().max()) else _acc

    @property
    def max_deceleration_power(self) -> float:
        deceleration = self.type_filter("D")
        return 0.0 if np.isnan(_dec := deceleration["power"].abs().max()) else _dec

    @property
    def action_aggregate(self) -> dict[str, Union[int, float]]:
        _action_aggregate = {
            "distance": self.distance,
            "maxSpeed": self.max_speed,
            "maxAcceleration": self.max_acceleration,
            "maxDeceleration": self.max_deceleration,
            "power": self.power,
            "maxPower": self.max_power,
            "sprintCount": self.sprint_count,
            "hsrCount": self.hsr_count,
            "accelerationCount": self.acceleration_count,
            "decelerationCount": self.deceleration_count,
            "sprintDistance": self.sprint_distance,
            "hsrDistance": self.hsr_distance,
            "accelerationDistance": self.acceleration_distance,
            "decelerationDistance": self.deceleration_distance,
            "minSprintDistance": self.min_sprint_distance,
            "maxSprintDistance": self.max_sprint_distance,
            "avgSprintDistance": self.avg_sprint_distance,
            "maxSprintPower": self.max_sprint_power,
            "maxHsrPower": self.max_hsr_power,
            "maxAccelerationPower": self.max_acceleration_power,
            "maxDecelerationPower": self.max_deceleration_power,
        }
        return _action_aggregate
