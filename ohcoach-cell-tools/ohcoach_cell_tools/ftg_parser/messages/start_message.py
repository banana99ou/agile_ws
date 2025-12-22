import struct
from typing import NamedTuple, Tuple

from ohcoach_cell_tools.constants import START_EXPORT_COLUMNS


class StartMessage(NamedTuple):
    cell_serial_number: int
    product_id: bytes
    version_id: bytes
    product_version: bytes
    firmware_major_version: int
    firmware_minor_version: int
    esp32_firmware_version: bytes
    gnss_fix_time: int
    cumulative_op_time: int
    ble_id: bytes
    imu_cal_accx: float
    imu_cal_accy: float
    imu_cal_accz: float
    imu_cal_gyrx: float
    imu_cal_gyry: float
    imu_cal_gyrz: float
    imu_cal_magx: float
    imu_cal_magy: float
    imu_cal_magz: float

    start_message_struct = struct.Struct("<H2s2s2sBB3sHI24sfffffffff")
    message_length = start_message_struct.size

    @classmethod
    def create(cls, payload):
        instance = cls._make(cls.start_message_struct.unpack(payload))

        serial_number = struct.unpack(">H", struct.pack("<H", instance.cell_serial_number))[0]

        version_bytes = instance.esp32_firmware_version
        major, minor, patch = version_bytes[0], version_bytes[1], version_bytes[2]
        ble_id = instance.ble_id.split(b'\x00')[0].decode("utf-8")
        product_id = instance.product_id.decode("utf-8")
        version_id = instance.version_id.decode("utf-8")
        product_version = instance.product_version.decode("utf-8")

        instance = instance._replace(
            cell_serial_number=serial_number,
            esp32_firmware_version=f"{major}.{minor}.{patch}",
            ble_id=ble_id,
            product_id=product_id,
            version_id=version_id,
            product_version=product_version
        )
        return instance

    def export_row(self) -> Tuple:
        return tuple(getattr(self, column) for column in START_EXPORT_COLUMNS)

    @property
    def device_model(self):
        try:
            decoded_product_id = self.product_id.decode("utf-8")[::-1]
            decoded_version_id = self.version_id.decode("utf-8")[::-1]
            return f"{decoded_product_id}{decoded_version_id}"
        except UnicodeError:
            return "[ERR: device_model]"

    @property
    def device_version(self):
        try:
            return self.product_version.decode("utf-8")[::-1]
        except UnicodeError:
            return "[ERR: device_version]"

    @property
    def device_number(self):
        return self.cell_serial_number

    @property
    def firmware_version(self):
        return f"v{self.firmware_major_version}.{self.firmware_minor_version}"

    @property
    def ble_hr_id(self):
        try:
            return self.ble_id
        except UnicodeError:
            return "[ERR: ble_hr_id]"

    @property
    def imu_accel_calibration(self):
        return (self.imu_cal_accx, self.imu_cal_accy, self.imu_cal_accz)

    @property
    def imu_gyro_calibration(self):
        return (self.imu_cal_gyrx, self.imu_cal_gyry, self.imu_cal_gyrz)

    @property
    def imu_magnet_calibration(self):
        return (self.imu_cal_magx, self.imu_cal_magy, self.imu_cal_magz)
