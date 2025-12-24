#!/usr/bin/env python3
"""
Simple ROS 2 bag inspector and exporter.

Features:
- List topics and their types/counts inside a ros2 bag.
- Export all messages of a topic to a CSV file (easy to open in Excel).

Requirements:
- Run this inside a ROS 2 Python environment (so that rosbag2_py, rclpy, etc. are available).

Examples:
  List topics in a bag:
    python3 ros2_bag_inspector.py list /path/to/bag_directory

  Export one topic to CSV:
    python3 ros2_bag_inspector.py export /path/to/bag_directory \\
        --topic /your/topic/name --out topic_data.csv
"""

import argparse
import csv
import json
import os
import sys
from typing import Dict, Tuple

import yaml

try:
    import rosbag2_py
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message
    from rosidl_runtime_py import message_to_ordereddict
except ImportError as exc:
    print(
        "Failed to import ROS 2 Python packages.\n"
        "Make sure you run this script in a ROS 2 environment, e.g.:\n"
        "  source /opt/ros/<distro>/setup.bash\n"
        "  source install/setup.bash (if you have a workspace)\n"
    )
    raise


def _detect_storage_id(bag_path: str) -> str:
    """
    Try to detect the storage backend (e.g. sqlite3, mcap) from metadata.yaml.
    Fallback to 'sqlite3' if not found.
    """
    meta_path = os.path.join(bag_path, "metadata.yaml")
    if not os.path.exists(meta_path):
        return "sqlite3"

    try:
        with open(meta_path, "r") as f:
            meta = yaml.safe_load(f) or {}
    except Exception:
        # If metadata cannot be read/parsed, fall back to sqlite3
        return "sqlite3"

    # Common layouts used by rosbag2
    storage_id = (
        meta.get("storage_identifier")
        or meta.get("storage_id")
        or meta.get("storage")
    )
    if not storage_id:
        info = meta.get("rosbag2_bagfile_information", {})
        storage_id = (
            info.get("storage_identifier")
            or info.get("storage_id")
            or info.get("storage")
        )

    return storage_id or "sqlite3"


def open_bag_reader(bag_path: str) -> Tuple[rosbag2_py.SequentialReader, Dict[str, str]]:
    """Open a ros2 bag for reading and return (reader, topic_type_map)."""
    if not os.path.isdir(bag_path):
        raise FileNotFoundError(f"Bag path is not a directory: {bag_path}")

    storage_id = _detect_storage_id(bag_path)

    storage_options = rosbag2_py.StorageOptions(
        uri=bag_path,
        storage_id=storage_id,
    )
    converter_options = rosbag2_py.ConverterOptions("", "")

    reader = rosbag2_py.SequentialReader()
    try:
        reader.open(storage_options, converter_options)
    except RuntimeError as e:
        raise RuntimeError(
            f"Failed to open bag at '{bag_path}' with storage_id '{storage_id}'.\n"
            f"Original error: {e}\n"
            f"- Check that this is the actual bag directory (it should contain 'metadata.yaml').\n"
            f"- Ensure you have read permissions and the disk is accessible.\n"
        ) from e

    topic_type_map: Dict[str, str] = {}
    for t in reader.get_all_topics_and_types():
        topic_type_map[t.name] = t.type

    return reader, topic_type_map


def list_bag_topics(bag_path: str) -> None:
    """Print topics, types, and approximate message counts for a bag."""
    reader, topic_type_map = open_bag_reader(bag_path)

    # Initialize counts
    counts: Dict[str, int] = {name: 0 for name in topic_type_map.keys()}

    # Iterate once through the bag to count messages
    while reader.has_next():
        topic, _, _ = reader.read_next()
        if topic in counts:
            counts[topic] += 1

    print(f"Bag: {bag_path}")
    print("Topics found:")
    for topic, msg_type in sorted(topic_type_map.items()):
        print(f"  {topic}  |  {msg_type}  |  messages: {counts.get(topic, 0)}")


def export_topic_to_csv(bag_path: str, topic_name: str, out_csv: str) -> None:
    """
    Export all messages of a single topic to a CSV file.

    Columns:
      - timestamp (ROS time, seconds as float)
      - topic
      - message_json (all fields as JSON text)
    """
    reader, topic_type_map = open_bag_reader(bag_path)

    if topic_name not in topic_type_map:
        print(f"Topic '{topic_name}' not found in bag.")
        print("Available topics:")
        for t in sorted(topic_type_map.keys()):
            print(f"  {t}")
        sys.exit(1)

    type_str = topic_type_map[topic_name]
    msg_type = get_message(type_str)

    # Prepare CSV writer
    fieldnames = ["timestamp", "topic", "message_json"]
    os.makedirs(os.path.dirname(os.path.abspath(out_csv)), exist_ok=True)
    total_written = 0

    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        while reader.has_next():
            topic, data, t = reader.read_next()
            if topic != topic_name:
                continue

            msg = deserialize_message(data, msg_type)
            msg_dict = message_to_ordereddict(msg)

            # Convert ROS time (nanoseconds) to float seconds for convenience
            timestamp_sec = t / 1e9

            writer.writerow(
                {
                    "timestamp": f"{timestamp_sec:.9f}",
                    "topic": topic,
                    "message_json": json.dumps(msg_dict),
                }
            )
            total_written += 1

    print(
        f"Exported {total_written} messages from topic '{topic_name}' "
        f"to CSV file: {out_csv}"
    )


def export_all_topics_to_csv(bag_path: str, out_csv: str) -> None:
    """
    Export all messages from all topics into a single CSV file.

    Columns:
      - timestamp (ROS time, seconds as float)
      - topic
      - type
      - message_json (all fields as JSON text)
    """
    reader, topic_type_map = open_bag_reader(bag_path)

    # Cache for message classes per ROS type string
    msg_type_cache: Dict[str, type] = {}

    fieldnames = ["timestamp", "topic", "type", "message_json"]
    os.makedirs(os.path.dirname(os.path.abspath(out_csv)), exist_ok=True)
    total_written = 0

    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        while reader.has_next():
            topic, data, t = reader.read_next()
            type_str = topic_type_map.get(topic)
            if not type_str:
                # Unknown topic type; skip (should not normally happen)
                continue

            if type_str not in msg_type_cache:
                msg_type_cache[type_str] = get_message(type_str)
            msg_type = msg_type_cache[type_str]

            msg = deserialize_message(data, msg_type)
            msg_dict = message_to_ordereddict(msg)

            timestamp_sec = t / 1e9

            writer.writerow(
                {
                    "timestamp": f"{timestamp_sec:.9f}",
                    "topic": topic,
                    "type": type_str,
                    "message_json": json.dumps(msg_dict),
                }
            )
            total_written += 1

    print(
        f"Exported {total_written} messages from all topics in '{bag_path}' "
        f"to CSV file: {out_csv}"
    )


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect and export ROS 2 bag files."
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # list command
    p_list = subparsers.add_parser(
        "list",
        help="List topics, types, and message counts in a bag.",
    )
    p_list.add_argument(
        "bag_path",
        help="Path to the ros2 bag directory (the folder created by 'ros2 bag record').",
    )

    # export command
    p_export = subparsers.add_parser(
        "export",
        help="Export all messages of one topic to a CSV file.",
    )
    p_export.add_argument(
        "bag_path",
        help="Path to the ros2 bag directory.",
    )
    p_export.add_argument(
        "--topic",
        required=True,
        help="Topic name to export (must exist in the bag).",
    )
    p_export.add_argument(
        "--out",
        required=True,
        help="Output CSV file path (e.g. topic_data.csv).",
    )

    # export-all command
    p_export_all = subparsers.add_parser(
        "export-all",
        help="Export all messages from all topics to a single CSV file.",
    )
    p_export_all.add_argument(
        "bag_path",
        help="Path to the ros2 bag directory.",
    )
    p_export_all.add_argument(
        "--out",
        required=True,
        help="Output CSV file path (e.g. all_topics.csv).",
    )

    return parser.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)

    if args.command == "list":
        list_bag_topics(args.bag_path)
    elif args.command == "export":
        export_topic_to_csv(args.bag_path, args.topic, args.out)
    elif args.command == "export-all":
        export_all_topics_to_csv(args.bag_path, args.out)
    else:
        raise RuntimeError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()


