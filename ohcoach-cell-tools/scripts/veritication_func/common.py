import json
import os

COMPUTED = "computed"
ACTION = "action"
COMPUTED_PATH = "results/computed"
ACTION_PATH = "results/action"
INTERVAL_SUMMARY_PATH = "results/interval_summary"
SESSION_PATH = "results/session"
SPEED_ZONE1 = [0, 7.2]
SPEED_ZONE2 = [7.2, 14.4]
SPEED_ZONE3 = [14.4, 19.8]
SPEED_ZONE4 = [19.8, 25.2]
SPEED_ZONE5 = [25.2]


def make_path_and_create_folders(path: str) -> tuple[str, str, str, str]:
    paths = (
        os.path.join(path, COMPUTED_PATH),
        os.path.join(path, ACTION_PATH),
        os.path.join(path, INTERVAL_SUMMARY_PATH),
        os.path.join(path, SESSION_PATH),
    )
    for dir_path in paths:
        os.makedirs(dir_path, exist_ok=True)

    return paths


def get_file_list(source: str) -> list[str]:
    if os.path.isfile(source):
        return [source]

    return sorted([path for file in os.listdir(source) if (path := os.path.join(source, file))])


def save_json(aggregate: dict, result_dir: str, file_name: str):
    action_aggregate_path = f"{result_dir}/{file_name}"

    with open(action_aggregate_path, "w") as outfile:
        json.dump(aggregate, outfile, indent=4)
