import json
from typing import Union

import pandas as pd

from scripts.veritication_func.common import (
    SPEED_ZONE1,
    SPEED_ZONE2,
    SPEED_ZONE3,
    SPEED_ZONE4,
    SPEED_ZONE5,
)


class ComputedAggregate:
    @property
    def df(self):
        return self._df

    @df.setter
    def df(self, df):
        self._df = df

    def create_computed_aggreagte_json(self, result_dir, file_name):
        computed_aggregate = self.computed_aggregate
        computed_aggregate_path = f"{result_dir}/{file_name}"

        with open(computed_aggregate_path, "w") as outfile:
            json.dump(computed_aggregate, outfile, indent=4)

    def calculate_distance_zone(self, zone_standard) -> float:
        computed_csv = self._df
        filter_df = computed_csv[
            (zone_standard[0] < computed_csv["distance"])
            & (computed_csv["distance"] < zone_standard[1])
        ]
        return filter_df["distance"].sum()

    @property
    def abs_power(self) -> pd.Series:
        power = self._df["power"].abs()
        return power

    @property
    def duration(self) -> float:
        return self._df["duration"].sum() / 60

    @property
    def total_distance(self) -> float:
        return self._df["distance"].sum()

    @property
    def max_total_distance(self) -> float:
        return self._df["distance"].max()

    @property
    def min_total_distance(self) -> float:
        return self._df["distance"].min()

    @property
    def avg_total_distance(self) -> float:
        return self._df["distance"].mean()

    @property
    def distance_per_mins(self) -> float:
        return self.total_distance / self.duration

    @property
    def distance_zone_1(self) -> float:
        return self.calculate_distance_zone(SPEED_ZONE1)

    @property
    def distance_zone_2(self) -> float:
        return self.calculate_distance_zone(SPEED_ZONE2)

    @property
    def distance_zone_3(self) -> float:
        return self.calculate_distance_zone(SPEED_ZONE3)

    @property
    def distance_zone_4(self) -> float:
        return self.calculate_distance_zone(SPEED_ZONE4)

    @property
    def distance_zone_5(self) -> float:
        computed_csv = self._df
        filter_df = computed_csv[SPEED_ZONE5[0] < computed_csv["distance"]]
        return filter_df["distance"].sum()

    @property
    def max_speed(self) -> float:
        return self._df["speed"].max()

    @property
    def max_acceleration(self) -> Union[int, float]:
        _max = self._df["accel"].max()
        return max(0, _max)

    @property
    def max_deceleration(self) -> Union[int, float]:
        _min = self._df["accel"].min() * -1
        return max(0, _min)

    @property
    def workload(self) -> float:
        return self._df["workload"].sum() / 100000

    @property
    def power(self) -> float:
        power_series = self.abs_power
        return power_series.sum()

    @property
    def max_power(self) -> float:
        power_series = self.abs_power
        return power_series.max()

    @property
    def min_power(self) -> float:
        power_series = self.abs_power
        return power_series.min()

    @property
    def avg_power(self) -> float:
        power_series = self.abs_power
        return power_series.mean()

    @property
    def computed_aggregate(self) -> dict[str, float]:
        _computed_aggregate = {
            "duration": self.duration,
            "totalDistance": self.total_distance,
            "maxTotalDistance": self.max_total_distance,
            "minTotalDistance": self.min_total_distance,
            "avgTotalDistance": self.avg_total_distance,
            "distancePerMins": self.distance_per_mins,
            "distanceZone1": self.distance_zone_1,
            "distanceZone2": self.distance_zone_2,
            "distanceZone3": self.distance_zone_3,
            "distanceZone4": self.distance_zone_4,
            "distanceZone5": self.distance_zone_5,
            "maxSpeed": self.max_speed,
            "maxAcceleration": self.max_acceleration,
            "maxDeceleration": self.max_deceleration,
            "workload": self.workload,
            "power": self.power,
            "maxPower": self.max_power,
            "minPower": self.min_power,
            "avgPower": self.avg_power,
        }
        return _computed_aggregate
