START_EXPORT_COLUMNS = (
    "device_model",
    "device_version",
    "device_number",
    "firmware_version",
    "esp32_firmware_version",
    "gnss_fix_time",
    "used_nand_block_size",
    "used_nand_page_size",
    "ble_hr_id",
    "imu_cal_accx",
    "imu_cal_accy",
    "imu_cal_accz",
    "imu_cal_gyrx",
    "imu_cal_gyry",
    "imu_cal_gyrz",
    "imu_cal_magx",
    "imu_cal_magy",
    "imu_cal_magz",
)

GPS_ORIGINAL_COLUMNS = [
    "date",
    "time_utc",
    "gps_nmea_latitude",
    "gps_nmea_longitude",
    "height_scaled",
    "h_acc_scaled",
    "v_acc_scaled",
    "sog_scaled",
    "course_angle_scaled",
    "vertical_velocity_scaled",
    "filtered_sog_scaled",
    "filtered_vertical_velocity_scaled",
    "gps_valid",
    "pdop",
    "navigation_satellites",
    "tracked_satellites",
    "avg_cn0_scaled",
    "pos_mode_byte",
]

GPS_EXPORT_COLUMNS = [
    "datetime",
    "nmea_latitude",
    "nmea_longitude",
    "latitude",
    "longitude",
    "speed",
    "height",
    "h_acc",
    "v_acc",
    "pdop",
    "course_angle",
    "vertical_velocity",
    "filtered_sog",
    "filtered_vertical_velocity",
    "gps_valid",
    "navigation_satellites",
    "tracked_satellites",
    "avg_cn0",
    "pos_mode",
]

IMU_ORIGINAL_COLUMNS = [
    "time_utc",
    "acc_x",
    "acc_y",
    "acc_z",
    "gyro_x",
    "gyro_y",
    "gyro_z",
    "magnet_x",
    "magnet_y",
    "magnet_z",
]

IMU_EXPORT_COLUMNS = [
    "datetime",
    "acc_x",
    "acc_y",
    "acc_z",
    "gyro_x",
    "gyro_y",
    "gyro_z",
    "magnet_x",
    "magnet_y",
    "magnet_z",
]

BS_EXPORT_COLUMNS = [
    "datetime",
    "operation_time",
    "hr",
    "voltage_mV",
    "current_mA",
    "cell_state",
    "internal_hr",
    "wifi_rssi",
    "power_detect_voltage",
    "orientation",
]

BS_ORIGINAL_COLUMNS = [
    "date",
    "time_utc",
    "operation_time",
    "hr",
    "battery_scaled",
    "cell_temperature_scaled",
    "cell_state",
    "internal_hr",
    "wifi_rssi",
    "power_detect_voltage",
    "orientation",
]

END_EXPORT_COLUMNS = (
    "power_off_indication",
    "battery_voltage",
    "operation_time",
    "used_nand_block_size",
    "used_nand_page_size",
)

LABEL_DATETIME = "datetime"
LABEL_LATITUDE = "latitude"
LABEL_LONGITUDE = "longitude"
LABEL_SPEED = "speed"
LABEL_POS_MODE = "pos_mode"

HEADER_RGP = [LABEL_DATETIME, LABEL_LATITUDE, LABEL_LONGITUDE, LABEL_SPEED]

LABEL_IMU_AX = "acc_x"
LABEL_IMU_AY = "acc_y"
LABEL_IMU_AZ = "acc_z"
LABEL_IMU_GX = "gyro_x"
LABEL_IMU_GY = "gyro_y"
LABEL_IMU_GZ = "gyro_z"
LABEL_IMU_MX = "magnet_x"
LABEL_IMU_MY = "magnet_y"
LABEL_IMU_MZ = "magnet_z"

HEADER_RIM = [
    LABEL_DATETIME,
    LABEL_IMU_AX,
    LABEL_IMU_AY,
    LABEL_IMU_AZ,
    LABEL_IMU_GX,
    LABEL_IMU_GY,
    LABEL_IMU_GZ,
    LABEL_IMU_MX,
    LABEL_IMU_MY,
    LABEL_IMU_MZ,
]

LABEL_OPERATION_TIME = "operation_time"
LABEL_HR = "hr"
HEADER_RBS = [
    LABEL_DATETIME,
    LABEL_OPERATION_TIME,
    LABEL_HR,
]

LABEL_LOCALTIME = "local_time"
HEADER_RAW_DATA = [
    LABEL_LOCALTIME,
    LABEL_LATITUDE,
    LABEL_LONGITUDE,
    f"{LABEL_SPEED}(km/h)",
    f"{LABEL_HR}(bpm)",
]

HEADER_OCH = HEADER_RGP

BYTES_ACC = 6
BYTES_GYRO = 6
BYTES_MAGNET = 6

FORMAT_INITIAL_DATETIME_YYMMDDHHII = "ymdhi"
FORMAT_DATETIME_SSFF = "sf"
