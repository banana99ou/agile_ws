#!/usr/bin/env python3
import math
import os
import sys

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

from sensor_msgs.msg import NavSatFix, NavSatStatus, Imu


def quat_to_yaw(q):
    """
    Convert quaternion to yaw (Z axis, ENU).
    yaw = atan2(2*(w*z + x*y), 1 - 2*(y^2 + z^2))
    """
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


def fix_status_to_string(status: int) -> str:
    """Interpret NavSatStatus.status."""
    if status < 0:
        return "NO_FIX"
    if status == NavSatStatus.STATUS_FIX:
        return "FIX"
    if status == NavSatStatus.STATUS_SBAS_FIX:
        return "SBAS_FIX"
    if status == NavSatStatus.STATUS_GBAS_FIX:
        return "GBAS_FIX"
    return f"UNKNOWN({status})"


class GPSStatusDisplay(Node):
    def __init__(self):
        super().__init__('gps_status_display')

        # Parameters so you can override topics without editing code
        self.declare_parameter('fix_topic', '/pixhawk/global_position/raw/fix')
        self.declare_parameter('imu_topic', '/pixhawk/imu/data')  # <-- FIXED default
        self.declare_parameter('print_rate_hz', 2.0)

        self.fix_topic = self.get_parameter('fix_topic').get_parameter_value().string_value
        self.imu_topic = self.get_parameter('imu_topic').get_parameter_value().string_value
        print_rate_hz = self.get_parameter('print_rate_hz').get_parameter_value().double_value
        print_period = 1.0 / max(print_rate_hz, 0.1)

        # Latest messages
        self.last_fix = None
        self.last_fix_time = None
        self.last_heading_rad = None
        self.last_heading_time = None

        # Subscriptions (sensor QoS is safer for high-rate streams)
        self.sub_fix = self.create_subscription(
            NavSatFix,
            self.fix_topic,
            self.fix_callback,
            qos_profile_sensor_data,
        )

        self.sub_imu = self.create_subscription(
            Imu,
            self.imu_topic,
            self.imu_callback,
            qos_profile_sensor_data,
        )

        # Timer to periodically print status
        self.timer = self.create_timer(print_period, self.print_status)

        self.get_logger().info(
            f"GPSStatusDisplay started.\n"
            f"  Fix topic: {self.fix_topic}\n"
            f"  IMU topic: {self.imu_topic}\n"
            f"  Print rate: {print_rate_hz:.1f} Hz"
        )

    def fix_callback(self, msg: NavSatFix):
        self.last_fix = msg
        self.last_fix_time = self.get_clock().now()

    def imu_callback(self, msg: Imu):
        # Some IMUs might publish invalid quaternions at startup.
        # Guard against NaNs.
        try:
            yaw = quat_to_yaw(msg.orientation)
            if math.isnan(yaw):
                return
            self.last_heading_rad = yaw
            self.last_heading_time = self.get_clock().now()
        except Exception:
            return

    def print_status(self):
        # Clear screen for a "live dashboard" feel
        if sys.stdout.isatty():
            os.system('clear')

        print("=== GPS / IMU Status ===")
        print(f"Fix topic: {self.fix_topic}")
        print(f"IMU topic: {self.imu_topic}")

        now = self.get_clock().now()

        # --- GPS ---
        if self.last_fix is None or self.last_fix_time is None:
            print("\nGPS: waiting for fix message ...")
        else:
            age = (now - self.last_fix_time).nanoseconds / 1e9
            lat = self.last_fix.latitude
            lon = self.last_fix.longitude
            alt = self.last_fix.altitude
            fix_str = fix_status_to_string(self.last_fix.status.status)

            # Common indoor/no-fix symptom: 0,0
            zero_pos = (abs(lat) < 1e-12 and abs(lon) < 1e-12)

            print("\nGPS:")
            print(f"  Fix status   : {fix_str}")
            print(f"  Latitude     : {lat:.7f}")
            print(f"  Longitude    : {lon:.7f}")
            print(f"  Altitude [m] : {alt:.3f}")
            print(f"  Age [s]      : {age:.2f}")

            if fix_str == "NO_FIX" or zero_pos:
                print("  Note         : Likely no sky view / no fix yet.")

        # --- Heading from IMU ---
        if self.last_heading_rad is None or self.last_heading_time is None:
            print("\nHeading (IMU): waiting for IMU message ...")
        else:
            age_h = (now - self.last_heading_time).nanoseconds / 1e9
            heading_deg = math.degrees(self.last_heading_rad)
            heading_deg = (heading_deg + 360.0) % 360.0

            print("\nHeading (IMU):")
            print(f"  Yaw [deg]    : {heading_deg:7.2f}")
            print(f"  Age [s]      : {age_h:.2f}")

        print("\n(CTRL+C to quit)")


def main(args=None):
    rclpy.init(args=args)
    node = GPSStatusDisplay()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
