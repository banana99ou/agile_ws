#!/usr/bin/env python3

import sys
import math
import time
import argparse
from typing import Optional

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry


def quat_to_yaw_z(q) -> float:
    """
    Planar assumption (x = y = 0):
    yaw = atan2(2*w*z, 1 - 2*z^2)
    """
    return math.atan2(2.0 * q.w * q.z, 1.0 - 2.0 * q.z * q.z)


def normalize_angle(a: float) -> float:
    """Wrap angle to [-pi, pi]."""
    while a > math.pi:
        a -= 2.0 * math.pi
    while a < -math.pi:
        a += 2.0 * math.pi
    return a


class OdomWatcher(Node):
    """
    Simple node to watch /wheel/odom and drive /cmd_vel
    for experiment scenarios.
    """

    def __init__(self):
        super().__init__("limo_scenario_motion")

        self.sub = self.create_subscription(
            Odometry,
            "/wheel/odom",
            self.odom_callback,
            10,
        )
        self.pub = self.create_publisher(Twist, "cmd_vel", 10)

        self.last_x: Optional[float] = None
        self.last_y: Optional[float] = None
        self.last_yaw: Optional[float] = None
        self.last_vx: Optional[float] = None
        self.last_time: Optional[float] = None  # ROS time (sec)

    def odom_callback(self, msg: Odometry):
        self.last_x = msg.pose.pose.position.x
        self.last_y = msg.pose.pose.position.y
        self.last_yaw = quat_to_yaw_z(msg.pose.pose.orientation)
        self.last_vx = msg.twist.twist.linear.x

        t = self.get_clock().now().seconds_nanoseconds()[0] + \
            self.get_clock().now().seconds_nanoseconds()[1] * 1e-9
        self.last_time = t

    # ------------- shared helpers -------------

    def wait_for_odom(self, timeout: float = 10.0) -> bool:
        """Block until we receive odom or timeout (seconds)."""
        self.get_logger().info("Waiting for /wheel/odom...")
        start = time.time()
        while rclpy.ok() and (self.last_x is None or self.last_y is None or self.last_yaw is None):
            rclpy.spin_once(self, timeout_sec=0.1)
            if timeout > 0.0 and (time.time() - start) > timeout:
                self.get_logger().warn("Timeout waiting for /wheel/odom")
                return False
        return self.last_x is not None and self.last_y is not None and self.last_yaw is not None

    def stop_robot(self):
        twist = Twist()
        self.pub.publish(twist)

    # ------------- scenario: static -------------

    def run_static_heading(self, heading_deg: float, max_omega: float = 0.6, k_yaw: float = 2.0,
                           yaw_tolerance_deg: float = 2.0, hold_time: float = 2.0, rate_hz: float = 20.0):
        """
        Rotate in-place to desired heading (odom frame), then stay still.
        """
        logger = self.get_logger()

        if not self.wait_for_odom():
            logger.error("No odom; cannot run static scenario.")
            return

        desired_yaw = math.radians(heading_deg)
        yaw_tol = math.radians(yaw_tolerance_deg)
        dt = 1.0 / rate_hz

        logger.info(
            f"[static] Target heading={heading_deg:.1f} deg, "
            f"max_omega={max_omega:.2f} rad/s, tol={yaw_tolerance_deg:.1f} deg"
        )

        # Rotate until within tolerance
        while rclpy.ok():
            rclpy.spin_once(self, timeout_sec=0.0)
            if self.last_yaw is None:
                continue

            yaw_err = normalize_angle(desired_yaw - self.last_yaw)

            if abs(yaw_err) <= yaw_tol:
                logger.info(
                    f"[static] Reached heading: "
                    f"current={math.degrees(self.last_yaw):.2f} deg, "
                    f"err={math.degrees(yaw_err):.2f} deg"
                )
                break

            omega = k_yaw * yaw_err
            omega = max(min(omega, max_omega), -max_omega)

            twist = Twist()
            twist.angular.z = omega
            self.pub.publish(twist)

            time.sleep(dt)

        # Hold still
        logger.info(f"[static] Holding still for {hold_time:.1f} s")
        end_time = time.time() + hold_time
        while rclpy.ok() and time.time() < end_time:
            self.stop_robot()
            time.sleep(dt)

        self.stop_robot()
        logger.info("[static] Scenario finished.")

    # ------------- scenario: const_vel -------------

    def run_const_vel(
        self,
        speed: float,
        distance: float,
        max_omega: float = 0.4,
        k_yaw: float = 2.0,
        vel_tolerance: float = 0.05,
        max_duration: float = 60.0,
        rate_hz: float = 20.0,
    ):
        """
        Move in straight line at constant cmd velocity for given distance.
        Logs when actual vx is within vel_tolerance of cmd speed.
        """
        logger = self.get_logger()

        if distance <= 0.0:
            logger.error("Distance must be > 0 for const_vel scenario.")
            return

        if not self.wait_for_odom():
            logger.error("No odom; cannot run const_vel scenario.")
            return

        start_x = self.last_x
        start_y = self.last_y
        yaw_ref = self.last_yaw
        dt = 1.0 / rate_hz
        cmd_speed = abs(speed)
        logger.info(
            f"[const_vel] distance={distance:.2f} m, speed={cmd_speed:.2f} m/s, "
            f"yaw_ref={math.degrees(yaw_ref):.1f} deg"
        )

        reached_vel_flagged = False
        start_time = time.time()

        while rclpy.ok():
            rclpy.spin_once(self, timeout_sec=0.0)

            if self.last_x is None or self.last_y is None or self.last_yaw is None:
                continue

            dx = self.last_x - start_x
            dy = self.last_y - start_y
            dist = math.sqrt(dx * dx + dy * dy)

            if dist >= distance:
                logger.info(
                    f"[const_vel] Reached distance: dist={dist:.3f} m "
                    f"(command={distance:.3f} m)"
                )
                break

            if (time.time() - start_time) > max_duration:
                logger.warn(
                    f"[const_vel] Max duration {max_duration:.1f} s exceeded; stopping."
                )
                break

            # Heading control to stay straight
            yaw_err = normalize_angle(self.last_yaw - yaw_ref)
            omega = -k_yaw * yaw_err
            omega = max(min(omega, max_omega), -max_omega)

            twist = Twist()
            twist.linear.x = cmd_speed
            twist.angular.z = omega
            self.pub.publish(twist)

            # Check velocity tracking flag (use odom vx)
            if self.last_vx is not None and not reached_vel_flagged:
                if abs(self.last_vx - cmd_speed) <= vel_tolerance:
                    now_ros = self.get_clock().now().to_msg()
                    logger.info(
                        f"[const_vel] Velocity tracking reached: "
                        f"t={now_ros.sec}.{now_ros.nanosec:09d}, "
                        f"cmd={cmd_speed:.3f} m/s, vx={self.last_vx:.3f} m/s "
                        f"(tol={vel_tolerance:.3f} m/s)"
                    )
                    reached_vel_flagged = True

            time.sleep(dt)

        self.stop_robot()
        logger.info("[const_vel] Scenario finished.")

    # ------------- scenario: const_acc -------------

    def run_const_acc(
        self,
        acc: float,
        distance: float,
        max_speed: float = 0.8,
        max_omega: float = 0.4,
        k_yaw: float = 2.0,
        acc_tolerance: float = 0.1,
        max_duration: float = 60.0,
        rate_hz: float = 20.0,
    ):
        """
        Move in straight line with constant commanded acceleration
        until distance reached or max_speed hit.
        Logs when estimated actual acceleration matches commanded acceleration.
        """
        logger = self.get_logger()

        if distance <= 0.0:
            logger.error("Distance must be > 0 for const_acc scenario.")
            return
        if acc == 0.0:
            logger.error("Acceleration must be non-zero for const_acc scenario.")
            return

        if not self.wait_for_odom():
            logger.error("No odom; cannot run const_acc scenario.")
            return

        start_x = self.last_x
        start_y = self.last_y
        yaw_ref = self.last_yaw
        dt = 1.0 / rate_hz

        cmd_speed = 0.0
        last_v_meas = self.last_vx
        last_t_meas = self.last_time
        reached_acc_flagged = False
        start_wall_time = time.time()

        logger.info(
            f"[const_acc] distance={distance:.2f} m, acc={acc:.2f} m/s^2, "
            f"max_speed={max_speed:.2f} m/s, yaw_ref={math.degrees(yaw_ref):.1f} deg"
        )

        while rclpy.ok():
            rclpy.spin_once(self, timeout_sec=0.0)

            if self.last_x is None or self.last_y is None or self.last_yaw is None:
                continue

            dx = self.last_x - start_x
            dy = self.last_y - start_y
            dist = math.sqrt(dx * dx + dy * dy)

            if dist >= distance:
                logger.info(
                    f"[const_acc] Reached distance: dist={dist:.3f} m "
                    f"(command={distance:.3f} m)"
                )
                break

            if (time.time() - start_wall_time) > max_duration:
                logger.warn(
                    f"[const_acc] Max duration {max_duration:.1f} s exceeded; stopping."
                )
                break

            # Update commanded speed (integrate acceleration)
            cmd_speed += acc * dt
            if acc > 0.0:
                cmd_speed = min(cmd_speed, max_speed)
            else:
                cmd_speed = max(cmd_speed, -max_speed)

            # Heading control to stay straight
            yaw_err = normalize_angle(self.last_yaw - yaw_ref)
            omega = -k_yaw * yaw_err
            omega = max(min(omega, max_omega), -max_omega)

            twist = Twist()
            twist.linear.x = cmd_speed
            twist.angular.z = omega
            self.pub.publish(twist)

            # Estimate actual acceleration and flag when ~acc
            if (
                self.last_vx is not None
                and self.last_time is not None
                and last_v_meas is not None
                and last_t_meas is not None
                and not reached_acc_flagged
            ):
                dt_meas = self.last_time - last_t_meas
                if dt_meas > 0.0:
                    a_meas = (self.last_vx - last_v_meas) / dt_meas
                    if abs(a_meas - acc) <= acc_tolerance:
                        now_ros = self.get_clock().now().to_msg()
                        logger.info(
                            f"[const_acc] Acceleration tracking reached: "
                            f"t={now_ros.sec}.{now_ros.nanosec:09d}, "
                            f"cmd={acc:.3f} m/s^2, a_meas={a_meas:.3f} m/s^2 "
                            f"(tol={acc_tolerance:.3f} m/s^2)"
                        )
                        reached_acc_flagged = True

                last_v_meas = self.last_vx
                last_t_meas = self.last_time

            time.sleep(dt)

        self.stop_robot()
        logger.info("[const_acc] Scenario finished.")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="LIMO scenario motion script (static, const_vel, const_acc).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--scenario",
        type=str,
        choices=["static", "const_vel", "const_acc"],
        required=True,
        help="Scenario type to run.",
    )

    # static params
    parser.add_argument(
        "--heading-deg",
        type=float,
        default=0.0,
        help="Target heading in degrees (odom frame) for static scenario.",
    )

    # const_vel params
    parser.add_argument(
        "--speed",
        type=float,
        default=0.3,
        help="Forward speed (m/s) for const_vel scenario.",
    )
    parser.add_argument(
        "--distance",
        type=float,
        default=1.0,
        help="Distance (m) to travel for const_vel/const_acc scenarios.",
    )
    parser.add_argument(
        "--vel-tolerance",
        type=float,
        default=0.05,
        help="Tolerance for actual vx vs cmd speed (m/s).",
    )

    # const_acc params
    parser.add_argument(
        "--acc",
        type=float,
        default=0.5,
        help="Commanded acceleration (m/s^2) for const_acc scenario.",
    )
    parser.add_argument(
        "--acc-tolerance",
        type=float,
        default=0.1,
        help="Tolerance for actual vs cmd acceleration (m/s^2).",
    )
    parser.add_argument(
        "--max-speed",
        type=float,
        default=0.8,
        help="Speed limit (m/s) when integrating acceleration.",
    )

    # general safety
    parser.add_argument(
        "--max-duration",
        type=float,
        default=60.0,
        help="Max duration (s) for motion scenarios before auto-stop.",
    )
    parser.add_argument(
        "--rate-hz",
        type=float,
        default=20.0,
        help="Control loop rate (Hz).",
    )

    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    rclpy.init()
    node = OdomWatcher()

    try:
        if args.scenario == "static":
            node.run_static_heading(
                heading_deg=args.heading_deg,
                rate_hz=args.rate_hz,
            )
        elif args.scenario == "const_vel":
            node.run_const_vel(
                speed=args.speed,
                distance=args.distance,
                vel_tolerance=args.vel_tolerance,
                max_duration=args.max_duration,
                rate_hz=args.rate_hz,
            )
        elif args.scenario == "const_acc":
            node.run_const_acc(
                acc=args.acc,
                distance=args.distance,
                max_speed=args.max_speed,
                acc_tolerance=args.acc_tolerance,
                max_duration=args.max_duration,
                rate_hz=args.rate_hz,
            )
        else:
            node.get_logger().error(f"Unknown scenario: {args.scenario}")
    except KeyboardInterrupt:
        node.get_logger().info("KeyboardInterrupt received, stopping robot.")
    finally:
        node.stop_robot()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main(sys.argv[1:])


