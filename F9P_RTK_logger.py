#!/usr/bin/env python3
import csv
import math
import os
from datetime import datetime

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import NavSatFix
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist

# MAVROS GPS raw: fix_type includes RTK_FLOAT/FIXED
from mavros_msgs.msg import GPSRAW


def quat_to_yaw(q):
    """Quaternion -> yaw (ENU)."""
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


class F9PRtkCsvLogger(Node):
    def __init__(self):
        super().__init__("f9p_rtk_csv_logger")

        # ---- Parameters ----
        self.declare_parameter("out_dir", os.path.expanduser("~/gnss_logs"))
        self.declare_parameter("file_prefix", "f9p_rtk")
        self.declare_parameter("log_hz", 10.0)  # CSV row rate (not necessarily GNSS rate)

        self.declare_parameter("topic_fix", "/pixhawk/global_position/raw/fix")
        self.declare_parameter("topic_gpsraw", "/pixhawk/gpsstatus/gps1/raw")
        self.declare_parameter("topic_wheel_odom", "/wheel/odom")
        self.declare_parameter("topic_cmd_vel", "/cmd_vel")

        out_dir = self.get_parameter("out_dir").get_parameter_value().string_value
        prefix = self.get_parameter("file_prefix").get_parameter_value().string_value
        log_hz = float(self.get_parameter("log_hz").get_parameter_value().double_value)

        self.topic_fix = self.get_parameter("topic_fix").get_parameter_value().string_value
        self.topic_gpsraw = self.get_parameter("topic_gpsraw").get_parameter_value().string_value
        self.topic_wheel_odom = self.get_parameter("topic_wheel_odom").get_parameter_value().string_value
        self.topic_cmd_vel = self.get_parameter("topic_cmd_vel").get_parameter_value().string_value

        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.csv_path = os.path.join(out_dir, f"{prefix}_{ts}.csv")

        # ---- Latest values (updated by callbacks) ----
        self.last_fix = None
        self.last_gpsraw = None
        self.last_odom = None
        self.last_cmd = None

        # For GPS accel (derived)
        self.prev_gps_speed = None
        self.prev_gps_speed_t = None
        self.last_gps_accel = None

        # ---- Subscriptions ----
        self.create_subscription(NavSatFix, self.topic_fix, self.cb_fix, 50)
        self.create_subscription(GPSRAW, self.topic_gpsraw, self.cb_gpsraw, 50)
        self.create_subscription(Odometry, self.topic_wheel_odom, self.cb_odom, 50)
        self.create_subscription(Twist, self.topic_cmd_vel, self.cb_cmd, 50)

        # ---- CSV writer ----
        self._f = open(self.csv_path, "w", newline="", buffering=1)
        self._w = csv.writer(self._f)

        self._w.writerow([
            # time
            "wall_time_iso",
            "ros_time_ns",

            # GNSS position
            "lat_deg",
            "lon_deg",
            "alt_m",
            "navsat_status",     # -1 no_fix, 0 fix (NavSatFix)
            "navsat_service",

            # RTK / GPSRAW
            "fix_type",          # MAVLink GPS_FIX_TYPE (0..)
            "rtk_float",         # 1 if fix_type==5
            "rtk_fixed",         # 1 if fix_type==6
            "satellites_visible",
            "gps_speed_mps",     # from GPSRAW.vel (cm/s -> m/s)
            "gps_accel_mps2",    # derived from speed

            # wheel odom (actual)
            "odom_x_m",
            "odom_y_m",
            "odom_yaw_deg",
            "odom_vx_mps",
            "odom_omega_rps",

            # cmd_vel (commanded)
            "cmd_vx_mps",
            "cmd_omega_rps",
        ])

        period = 1.0 / max(log_hz, 1e-6)
        self.timer = self.create_timer(period, self.write_row)

        self.get_logger().info(f"Logging to CSV: {self.csv_path}")
        self.get_logger().info(f"Subscribing:\n"
                               f"  fix     : {self.topic_fix}\n"
                               f"  gpsraw  : {self.topic_gpsraw}\n"
                               f"  odom    : {self.topic_wheel_odom}\n"
                               f"  cmd_vel : {self.topic_cmd_vel}")

    def cb_fix(self, msg: NavSatFix):
        self.last_fix = msg

    def cb_gpsraw(self, msg: GPSRAW):
        self.last_gpsraw = msg

        # GPSRAW.vel is usually ground speed in cm/s (MAVLink GPS_RAW_INT)
        # Convert to m/s
        gps_speed = None
        try:
            gps_speed = float(msg.vel) * 0.01
        except Exception:
            gps_speed = None

        now = self.get_clock().now()
        now_s = now.nanoseconds * 1e-9

        if gps_speed is not None and self.prev_gps_speed is not None and self.prev_gps_speed_t is not None:
            dt = now_s - self.prev_gps_speed_t
            if dt > 1e-3:
                self.last_gps_accel = (gps_speed - self.prev_gps_speed) / dt

        self.prev_gps_speed = gps_speed
        self.prev_gps_speed_t = now_s

    def cb_odom(self, msg: Odometry):
        self.last_odom = msg

    def cb_cmd(self, msg: Twist):
        self.last_cmd = msg

    def _safe(self, v):
        return "" if v is None else v

    def write_row(self):
        now = self.get_clock().now()
        wall = datetime.now().isoformat(timespec="milliseconds")
        ros_ns = int(now.nanoseconds)

        # ---- NavSatFix ----
        lat = lon = alt = nav_status = nav_service = None
        if self.last_fix is not None:
            lat = float(self.last_fix.latitude)
            lon = float(self.last_fix.longitude)
            alt = float(self.last_fix.altitude)
            nav_status = int(self.last_fix.status.status)
            nav_service = int(self.last_fix.status.service)

        # ---- GPSRAW ----
        fix_type = sats = gps_speed = None
        rtk_float = rtk_fixed = None
        if self.last_gpsraw is not None:
            fix_type = int(self.last_gpsraw.fix_type)
            sats = int(self.last_gpsraw.satellites_visible)
            # vel in cm/s -> m/s
            gps_speed = float(self.last_gpsraw.vel) * 0.01
            rtk_float = 1 if fix_type == 5 else 0
            rtk_fixed = 1 if fix_type == 6 else 0

        gps_accel = self.last_gps_accel

        # ---- Odom ----
        ox = oy = oyaw_deg = ovx = oomega = None
        if self.last_odom is not None:
            ox = float(self.last_odom.pose.pose.position.x)
            oy = float(self.last_odom.pose.pose.position.y)
            oyaw = quat_to_yaw(self.last_odom.pose.pose.orientation)
            oyaw_deg = math.degrees(oyaw)
            ovx = float(self.last_odom.twist.twist.linear.x)
            oomega = float(self.last_odom.twist.twist.angular.z)

        # ---- Cmd ----
        cvx = comega = None
        if self.last_cmd is not None:
            cvx = float(self.last_cmd.linear.x)
            comega = float(self.last_cmd.angular.z)

        self._w.writerow([
            wall, ros_ns,
            self._safe(lat), self._safe(lon), self._safe(alt),
            self._safe(nav_status), self._safe(nav_service),
            self._safe(fix_type), self._safe(rtk_float), self._safe(rtk_fixed),
            self._safe(sats),
            self._safe(gps_speed),
            self._safe(gps_accel),
            self._safe(ox), self._safe(oy), self._safe(oyaw_deg),
            self._safe(ovx), self._safe(oomega),
            self._safe(cvx), self._safe(comega),
        ])

    def destroy_node(self):
        try:
            self._f.flush()
            self._f.close()
        except Exception:
            pass
        super().destroy_node()


def main():
    rclpy.init()
    node = F9PRtkCsvLogger()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
