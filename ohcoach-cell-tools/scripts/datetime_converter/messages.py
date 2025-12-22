import struct
from dataclasses import dataclass


def get_start_message() -> bytes:
    start_message_strcut = struct.Struct("<H2s2s2sBB3sHHH24sfffffffff")
    start_message_data = (
        41561,
        b"LC",
        b"XB",
        b"B4",
        5,
        9,
        b"226",
        55,
        0,
        0,
        b"Polar H10 5B96832C\x00\x00\x00\x00\x00\x00",
        -0.014404296875,
        0.01507568359375,
        -0.076904296875,
        -3.5572519302368164,
        3.244274854660034,
        -0.6564885377883911,
        1.19140625,
        1.1953125,
        1.15625,
    )

    return (
        b"COACH"
        + b"\x04"  # MSG_TYPE = 4
        + b"\x4f"  # MSG_LENGTH = 79
        + start_message_strcut.pack(*start_message_data)
        + b"\x6d"  # CRC = 109
        + b"\r\n"
    )


def get_end_message() -> bytes:
    end_message_struct = struct.Struct("<cHHHH")
    end_message_data = (
        b"N",
        372,
        6231,
        184,
        12,
    )

    return (
        b"COACH"
        + b"\x05"  # MSG_TYPE = 5
        + b"\x09"  # MSG_LENGTH = 9
        + end_message_struct.pack(*end_message_data)
        + b"\xcc"  # CRC = 204
        + b"\r\n"
    )


@dataclass
class GpsMessage:
    date: int
    time_utc: int
    gps_nmea_latitude: int
    gps_nmea_longitude: int
    height_scaled: int
    h_acc_scaled: int
    v_acc_scaled: int
    sog_scaled: int
    course_angle_scaled: int
    vertical_velocity_scaled: int
    hdop_scaled: int
    vdop_scaled: int
    tdop_scaled: int
    navigation_satellites: int
    tracked_satellites: int
    avg_cn0_scaled: int
    pos_mode_byte: bytes

    def __init__(self, gps_message: tuple):
        dt = getattr(gps_message, "datetime")
        self.date = dt.year | (dt.month << 16) | (dt.day << 24)
        self.time_utc = int(dt.microsecond / 10000) + 100 * (
            dt.second + 100 * (dt.minute + 100 * dt.hour)
        )
        self.gps_nmea_latitude = int(float(getattr(gps_message, "nmea_latitude")) * 1e8)
        self.gps_nmea_longitude = int(float(getattr(gps_message, "nmea_longitude")) * 1e8)
        self.sog_scaled = int(float(getattr(gps_message, "speed")) * 1e3)
        self.height_scaled = int(float(getattr(gps_message, "height")) * 1e3)
        self.h_acc_scaled = int(float(getattr(gps_message, "h_acc")) * 1e3)
        self.v_acc_scaled = int(float(getattr(gps_message, "v_acc")) * 1e3)
        self.course_angle_scaled = int(float(getattr(gps_message, "course_angle")) * 1e2)
        self.vertical_velocity_scaled = int(float(getattr(gps_message, "vertical_velocity")) * 1e3)
        self.hdop_scaled = int(float(getattr(gps_message, "hdop")) * 1e2)
        self.vdop_scaled = int(float(getattr(gps_message, "vdop")) * 1e2)
        self.tdop_scaled = int(float(getattr(gps_message, "tdop")) * 1e2)
        self.navigation_satellites = int(getattr(gps_message, "navigation_satellites"))
        self.tracked_satellites = int(getattr(gps_message, "tracked_satellites"))
        self.avg_cn0_scaled = int(getattr(gps_message, "avg_cn0"))
        self.pos_mode_byte = getattr(gps_message, "pos_mode").encode("utf-8")

    @property
    def payload(self) -> list:
        return [
            self.date,
            self.time_utc,
            self.gps_nmea_latitude,
            self.gps_nmea_longitude,
            self.height_scaled,
            self.h_acc_scaled,
            self.v_acc_scaled,
            self.sog_scaled,
            self.course_angle_scaled,
            self.vertical_velocity_scaled,
            self.hdop_scaled,
            self.vdop_scaled,
            self.tdop_scaled,
            self.navigation_satellites,
            self.tracked_satellites,
            self.avg_cn0_scaled,
            self.pos_mode_byte,
        ]


def get_gps_message_bytes(gps_message: tuple) -> bytes:
    gps_message_data = GpsMessage(gps_message=gps_message)
    gps_message_struct = struct.Struct("<IiqqIHHiHiHHHBBBc")

    crc_data = b"\x01" + b"\x34" + gps_message_struct.pack(*gps_message_data.payload)
    crc = 0
    for c in crc_data:
        crc ^= c

    return b"COACH" + crc_data + struct.pack("B", crc) + b"\r\n"


@dataclass
class ImuMessage:
    time_utc: int
    acc_x: int
    acc_y: int
    acc_z: int
    gyro_x: int
    gyro_y: int
    gyro_z: int
    magnet_x: int
    magnet_y: int
    magnet_z: int

    def __init__(self, imu_message: tuple):
        dt = getattr(imu_message, "datetime")
        self.time_utc = int(dt.microsecond / 10000) + 100 * (
            dt.second + 100 * (dt.minute + 100 * dt.hour)
        )
        self.acc_x = int(getattr(imu_message, "acc_x"))
        self.acc_y = int(getattr(imu_message, "acc_y"))
        self.acc_z = int(getattr(imu_message, "acc_z"))
        self.gyro_x = int(getattr(imu_message, "gyro_x"))
        self.gyro_y = int(getattr(imu_message, "gyro_y"))
        self.gyro_z = int(getattr(imu_message, "gyro_z"))
        self.magnet_x = int(getattr(imu_message, "magnet_x"))
        self.magnet_y = int(getattr(imu_message, "magnet_y"))
        self.magnet_z = int(getattr(imu_message, "magnet_z"))

    @property
    def time_utc_payload(self) -> list:
        return [self.time_utc]

    @property
    def accel_gyro_payload(self) -> list:
        return [self.acc_x, self.acc_y, self.acc_z, self.gyro_x, self.gyro_y, self.gyro_z]

    @property
    def magnet_payload(self) -> list:
        return [self.magnet_x, self.magnet_y, self.magnet_z]


def get_imu_message_bytes(imu_message: tuple) -> bytes:
    imu_message_data = ImuMessage(imu_message=imu_message)
    time_utc_struct = struct.Struct("<i")
    accel_gyro_struct = struct.Struct(">hhhhhh")
    magnet_struct = struct.Struct("<hhh")

    crc_data = (
        b"\x02"
        + b"\x16"
        + time_utc_struct.pack(*imu_message_data.time_utc_payload)
        + accel_gyro_struct.pack(*imu_message_data.accel_gyro_payload)
        + magnet_struct.pack(*imu_message_data.magnet_payload)
    )
    crc = 0
    for c in crc_data:
        crc ^= c

    return b"COACH" + crc_data + struct.pack("B", crc) + b"\r\n"


@dataclass
class BsMessage:
    date: int
    time_utc: int
    operation_time: int
    hr: int
    battery_scaled: int
    cell_temperature_scaled: int
    cell_state: int
    reserve_2: int
    reserve_3: int

    def __init__(self, bs_message: tuple):
        dt = getattr(bs_message, "datetime")
        self.date = dt.year | (dt.month << 16) | (dt.day << 24)
        self.time_utc = int(dt.microsecond / 10000) + 100 * (
            dt.second + 100 * (dt.minute + 100 * dt.hour)
        )
        self.operation_time = int(getattr(bs_message, "operation_time"))
        self.hr = int(getattr(bs_message, "hr"))
        self.battery_scaled = int(float(getattr(bs_message, "battery")) * 1e2)
        self.cell_temperature_scaled = int(float(getattr(bs_message, "cell_temperature")) * 1e2)
        self.cell_state = int(getattr(bs_message, "cell_state"))
        self.reserve_2 = int(getattr(bs_message, "reserve_2"))
        self.reserve_3 = int(getattr(bs_message, "reserve_3"))

    @property
    def payload(self) -> list:
        return [
            self.date,
            self.time_utc,
            self.operation_time,
            self.hr,
            self.battery_scaled,
            self.cell_temperature_scaled,
            self.cell_state,
            self.reserve_2,
            self.reserve_3,
        ]


def get_bs_message_bytes(bs_message: tuple) -> bytes:
    bs_message_data = BsMessage(bs_message=bs_message)
    bs_message_struct = struct.Struct("<IiIHHHHHH")

    crc_data = b"\x03" + b"\x18" + bs_message_struct.pack(*bs_message_data.payload)
    crc = 0
    for c in crc_data:
        crc ^= c

    return b"COACH" + crc_data + struct.pack("B", crc) + b"\r\n"
