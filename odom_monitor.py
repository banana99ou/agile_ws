#!/usr/bin/env python3
import math

import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry


def quat_to_yaw_z(q):
    """
    Assuming planar motion (x = y = 0).
    yaw = atan2(2*w*z, 1 - 2*z^2)
    """
    return math.atan2(2.0 * q.w * q.z, 1.0 - 2.0 * q.z * q.z)


class OdomMonitor(Node):
    def __init__(self):
        super().__init__('odom_monitor')
        self.sub = self.create_subscription(
            Odometry,
            '/wheel/odom',
            self.odom_callback,
            10
        )

        self.start_x = None
        self.start_y = None
        self.start_yaw = None
        self.start_time = None

        self.last_print_time = self.get_clock().now()
        self.last_x = None
        self.last_y = None
        self.last_yaw = None

        self.get_logger().info("Subscribed to /wheel/odom. Move the robot to see updates.")

    def odom_callback(self, msg: Odometry):
        x = msg.pose.pose.position.x
        y = msg.pose.pose.position.y
        yaw = quat_to_yaw_z(msg.pose.pose.orientation)  # rad

        now = self.get_clock().now()

        # Initialize start pose and time on first message
        if self.start_x is None:
            self.start_x = x
            self.start_y = y
            self.start_yaw = yaw
            self.start_time = now

        # distance from start
        dx = x - self.start_x
        dy = y - self.start_y
        dist = math.sqrt(dx * dx + dy * dy)

        # yaw in degrees
        yaw_deg = math.degrees(yaw)
        dyaw_deg = math.degrees(yaw - self.start_yaw)

        # rate limit printing & avoid spamming stationary zeros
        dt_print = (now - self.last_print_time).nanoseconds / 1e9

        # movement thresholds
        moved_enough = False
        if self.last_x is None:
            moved_enough = True
        else:
            ddx = x - self.last_x
            ddy = y - self.last_y
            dyaw_last = yaw - self.last_yaw
            step_dist = math.sqrt(ddx * ddx + ddy * ddy)
            step_yaw_deg = abs(math.degrees(dyaw_last))
            if step_dist > 0.005 or step_yaw_deg > 0.5:
                moved_enough = True

        if dt_print > 0.2 and moved_enough:
            self.last_print_time = now
            self.last_x = x
            self.last_y = y
            self.last_yaw = yaw

            # time since we started monitoring (approx)
            t_since_start = (now - self.start_time).nanoseconds / 1e9

            self.get_logger().info(
                f"t={t_since_start:5.1f}s | "
                f"x={x:6.3f} m, y={y:6.3f} m | "
                f"yaw={yaw_deg:6.1f}° | "
                f"dist_from_start={dist:6.3f} m | "
                f"Δyaw_from_start={dyaw_deg:6.1f}°"
            )


def main(args=None):
    rclpy.init(args=args)
    node = OdomMonitor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

