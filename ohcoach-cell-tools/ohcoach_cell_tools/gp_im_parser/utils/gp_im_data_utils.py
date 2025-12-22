from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class ReadableGPSData:
    df: pd.DataFrame
    postfix: str
    file_path: Optional[str] = None


@dataclass
class ReadableIMUData:
    df: pd.DataFrame
    postfix: str
    file_path: Optional[str] = None


@dataclass
class ImuData:
    im_stream: bytes
    device_version: str
    firmware_version: str
    frequency: int
