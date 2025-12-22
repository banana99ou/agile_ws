import os
from dataclasses import dataclass


@dataclass(init=True)
class CellInfo:
    """
    Ultimate dm-core 기준 Cell Name Information
    cell_file_name : {serial_number}_{firmware_version}_{error_count}_{unix_time}_{bad_sector_count}
    serial_number : {product_id}{version_id}-{product_version}-{production_number}
    product_id : CL
    version_id : BX
    product_version : 3A 이상 (2A ~ 2X 버전은 파일 명명법이 다르다)
    production_nubmer : cell number

    ex)
    device_model : CLBX
    device_version : 3A
    device_number : 33490
    firmware_version : 3.3
    """

    device_model: str
    device_version: str
    device_number: int
    firmware_version: str

    def __init__(self, file_path: str):
        cell_name = os.path.basename(file_path)
        cell_name_token = cell_name.split("_")
        serial_number = cell_name_token[0].split("-")

        self.device_model = serial_number[0]
        self.device_version = serial_number[1]
        self.device_number = int(serial_number[2])
        self.firmware_version = cell_name_token[1]
