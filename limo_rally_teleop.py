#!/usr/bin/env python3
import sys
import math
import time

import rclpy # pyright: ignore[reportMissingImports]
from rclpy.node import Node # pyright: ignore[reportMissingImports]
from geometry_msgs.msg import Twist # pyright: ignore[reportMissingImports]
from nav_msgs.msg import Odometry # pyright: ignore[reportMissingImports]
from sensor_msgs.msg import NavSatFix # pyright: ignore[reportMissingImports]
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy # pyright: ignore[reportMissingImports]

if sys.platform == 'win32':
    import msvcrt
else:
    import termios
    import tty


msg = """
Rally Teleop for LIMO (odom-based return, GPS-logged)
----------------------------------------------------
Normal driving (same as teleop_twist_keyboard):

   u    i    o
   j    k    l
   m    ,    .

For Holonomic mode (strafing), hold down the shift key:
   U    I    O
   J    K    L
   M    <    >

R : set rally point (current /wheel/odom + GPS)
t : go back to rally point (odom frame) and stop
g : go forward 1.0 m with yaw-hold (same as before)

q/z : increase/decrease max speeds by 10%
w/x : increase/decrease only linear speed by 10%
e/c : increase/decrease only angular speed by 10%

CTRL-C or hardware e-stop to quit
"""

moveBindings = {
    'i': (1, 0, 0, 0),
    'o': (1, 0, 0, -1),
    'j': (0, 0, 0, 1),
    'l': (0, 0, 0, -1),
    'u': (1, 0, 0, 1),
    ',': (-1, 0, 0, 0),
    '.': (-1, 0, 0, 1),
    'm': (-1, 0, 0, -1),
    'O': (1, -1, 0, 0),
    'I': (1, 0, 0, 0),
    'J': (0, 1, 0, 0),
    'L': (0, -1, 0, 0),
    'U': (1, 1, 0, 0),
    '<': (-1, 0, 0, 0),
    '>': (-1, -1, 0, 0),
    'M': (-1, 1, 0, 0),
}

speedBindings = {
    'q': (1.1, 1.1),
    'z': (.9, .9),
    'w': (1.1, 1),
    'x': (.9, 1),
    'e': (1, 1.1),
    'c': (1, .9),
}


def getKey(settings):
    if sys.platform == 'win32':
        key = msvcrt.getwch()
    else:
        tty.setraw(sys.stdin.fileno())
        key = sys.stdin.read(1)
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
    return key


def saveTerminalSettings():
    if sys.platform == 'win32':
        return None
    return termios.tcgetattr(sys.stdin)


def restoreTerminalSettings(old_settings):
    if sys.platform == 'win32':
        return
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


def vels(speed, turn):
    return f"currently:\tspeed {speed:.3f}\tturn {turn:.3f}"


def quat_to_yaw_z(q):
    """
    Planar assumption (x = y = 0):
    yaw = atan2(2*w*z, 1 - 2*z^2)
    """
    return math.atan2(2.0 * q.w * q.z, 1.0 - 2.0 * q.z * q.z)


def normalize_angle(a):
    """Wrap angle to [-pi, pi]."""
    while a > math.pi:
        a -= 2.0 * math.pi
    while a < -math.pi:
        a += 2.0 * math.pi
    return a


class StateWatcher(Node):
    def __init__(self):
        super().__init__('rally_teleop_state_watcher')

        # Odom
        self.odom_sub = self.create_subscription(
            Odometry,
            '/wheel/odom',
            self.odom_callback,
            10
        )
        self.last_x = None
        self.last_y = None
        self.last_yaw = None

        # QoS for MAVROS sensor topics (BEST_EFFORT)
        sensor_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
        )

        # GPS (Pixhawk via MAVROS)
        self.gps_sub = self.create_subscription(
            NavSatFix,
            '/pixhawk/global_position/raw/fix',
            self.gps_callback,
            sensor_qos,
        )
        self.last_lat = None
        self.last_lon = None

        # Rally point (odom + GPS snapshot)
        self.has_rally = False
        self.rally_x = None
        self.rally_y = None
        self.rally_lat = None
        self.rally_lon = None

    def odom_callback(self, msg: Odometry):
        self.last_x = msg.pose.pose.position.x
        self.last_y = msg.pose.pose.position.y
        self.last_yaw = quat_to_yaw_z(msg.pose.pose.orientation)

    def gps_callback(self, msg: NavSatFix):
        # Ignore invalid fixes
        if msg.status.status < 0:
            return
        self.last_lat = msg.latitude
        self.last_lon = msg.longitude

    def set_rally_point(self):
        if self.last_x is None or self.last_y is None:
            self.get_logger().warn("No odom yet, cannot set rally point.")
            return False
        if self.last_lat is None or self.last_lon is None or (
            abs(self.last_lat) < 1e-6 and abs(self.last_lon) < 1e-6
        ):
            self.get_logger().warn("No valid GPS yet, setting rally in odom only.")
        self.rally_x = self.last_x
        self.rally_y = self.last_y
        self.rally_lat = self.last_lat
        self.rally_lon = self.last_lon
        self.has_rally = True

        self.get_logger().info(
            f"Rally set at odom (x={self.rally_x:.3f}, y={self.rally_y:.3f}) "
            f"GPS (lat={self.rally_lat}, lon={self.rally_lon})"
        )
        return True


def run_segment_forward_yaw_hold(
    node: StateWatcher,
    pub,
    speed: float,
    distance: float,
    P: float = 1.0,
    D: float = 1.0,
    prev_yaw_err: float = 0,
    max_omega: float = 0.4,
    rate_hz: float = 20.0,
):
    """
    Drive forward 'distance' meters at 'speed' m/s using /wheel/odom:
      - use yaw at start as reference
      - apply yaw-hold: omega = -P * yaw_err - D * yaw_err_dot, saturated
    """
    logger = node.get_logger()

    logger.info("Waiting for /wheel/odom...")
    while rclpy.ok() and (node.last_x is None or node.last_y is None or node.last_yaw is None):
        rclpy.spin_once(node, timeout_sec=0.1)

    if node.last_x is None:
        logger.warn("No odom received; aborting segment.")
        return prev_yaw_err

    start_x = node.last_x
    start_y = node.last_y
    yaw_ref = node.last_yaw
    logger.info(
        f"Starting forward segment: distance={distance:.2f} m, "
        f"speed={speed:.2f} m/s, yaw_ref={math.degrees(yaw_ref):.1f}°"
    )

    dt = 1.0 / rate_hz

    while rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.0)

        if node.last_x is None or node.last_y is None or node.last_yaw is None:
            continue

        dx = node.last_x - start_x
        dy = node.last_y - start_y
        traveled = math.sqrt(dx * dx + dy * dy)

        if traveled >= distance:
            logger.info(f"Reached target distance: {traveled:.3f} m (command={distance:.3f} m)")
            break

        yaw_err = normalize_angle(node.last_yaw - yaw_ref)
        yaw_err_diff = (yaw_err - prev_yaw_err) / dt
        prev_yaw_err = yaw_err

        omega = - P * yaw_err
        print(f"omega: {omega}, P: {-P * yaw_err} D: {D * yaw_err_diff}")
        omega = max(min(omega, max_omega), -max_omega)

        twist = Twist()
        twist.linear.x = abs(speed)
        twist.angular.z = omega
        pub.publish(twist)

        time.sleep(dt)

    twist = Twist()
    pub.publish(twist)
    logger.info("Segment finished; robot stopped.")

    return yaw_err


def run_go_to_rally(
    node: StateWatcher,
    pub,
    speed: float = 0.3,
    max_omega: float = 0.5,
    P_yaw: float = 1.5,
    K_dist: float = 0.5,
    stop_dist: float = 0.1,
    rate_hz: float = 20.0,
):
    """
    Simple point-to-point controller in /wheel/odom frame:
      - Uses rally_x, rally_y as goal
      - Uses current odom (x, y, yaw)
      - Drives until within stop_dist
    GPS is not used for control here, only logged in node.rally_lat/lon.
    """
    logger = node.get_logger()

    if not node.has_rally or node.rally_x is None or node.rally_y is None:
        logger.warn("No rally point set; press 'R' first.")
        return

    logger.info(
        f"Going back to rally point at odom (x={node.rally_x:.3f}, y={node.rally_y:.3f}), "
        f"GPS approx (lat={node.rally_lat}, lon={node.rally_lon})"
    )

    logger.info("Waiting for /wheel/odom...")
    while rclpy.ok() and (node.last_x is None or node.last_y is None or node.last_yaw is None):
        rclpy.spin_once(node, timeout_sec=0.1)

    if node.last_x is None:
        logger.warn("No odom available, aborting go-to-rally.")
        return

    dt = 1.0 / rate_hz

    while rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.0)

        if node.last_x is None or node.last_y is None or node.last_yaw is None:
            continue

        dx = node.rally_x - node.last_x
        dy = node.rally_y - node.last_y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist <= stop_dist:
            logger.info(f"Reached rally (dist={dist:.3f} m <= {stop_dist:.3f} m).")
            break

        # Desired heading in odom frame
        desired_yaw = math.atan2(dy, dx)
        yaw_err = normalize_angle(desired_yaw - node.last_yaw)

        # Simple logic: if yaw error is large, rotate in place; otherwise drive + turn
        if abs(yaw_err) > math.radians(30.0):
            lin = 0.0
        else:
            lin = max(min(K_dist * dist, speed), 0.0)

        omega = P_yaw * yaw_err
        omega = max(min(omega, max_omega), -max_omega)

        twist = Twist()
        twist.linear.x = lin
        twist.angular.z = omega
        pub.publish(twist)

        time.sleep(dt)

    # Stop at the end
    twist = Twist()
    pub.publish(twist)
    logger.info("Go-to-rally finished; robot stopped.")


def main():
    settings = saveTerminalSettings()
    rclpy.init()

    node = StateWatcher()
    # Publish raw velocity commands; an external safety/E-stop node should
    # subscribe to `cmd_vel_raw` and publish filtered commands on `cmd_vel`.
    pub = node.create_publisher(Twist, 'cmd_vel_raw', 10)
    # pub = node.create_publisher(Twist, 'cmd_vel', 10)

    speed = 0.3   # default forward speed
    turn = 1.0
    x = y = z = th = 0.0
    status = 0
    prev_yaw_err = 0.0

    try:
        print(msg)
        print(vels(speed, turn))
        while rclpy.ok():
            # keep subscriptions alive so /wheel/odom and GPS callbacks run
            rclpy.spin_once(node, timeout_sec=0.0)
            key = getKey(settings)

            if key in moveBindings.keys():
                x = moveBindings[key][0]
                y = moveBindings[key][1]
                z = moveBindings[key][2]
                th = moveBindings[key][3]

            elif key in speedBindings.keys():
                speed = speed * speedBindings[key][0]
                turn = turn * speedBindings[key][1]
                print(vels(speed, turn))
                if status == 14:
                    print(msg)
                status = (status + 1) % 15

            elif key == 'g':
                # Yaw-hold forward segment: 1.0 m
                print("\n[g] segment: forward 1.0 m with /wheel/odom yaw-hold\n")
                x = y = z = th = 0.0
                twist = Twist()
                pub.publish(twist)  # stop before starting segment
                prev_yaw_err = run_segment_forward_yaw_hold(
                    node,
                    pub,
                    speed=speed,
                    distance=1.0,
                    P=1.0,
                    D=2.0,
                    prev_yaw_err=prev_yaw_err,
                    max_omega=0.4,
                    rate_hz=20.0,
                )
                print(vels(speed, turn))

            elif key == 'R':
                # Set rally point (odom + GPS)
                x = y = z = th = 0.0
                twist = Twist()
                pub.publish(twist)
                node.set_rally_point()

            elif key == 't':
                # Go back to rally point (odom-based)
                print("\n[t] Go-to-rally in odom frame\n")
                x = y = z = th = 0.0
                twist = Twist()
                pub.publish(twist)
                run_go_to_rally(
                    node,
                    pub,
                    speed=speed,
                    max_omega=0.5,
                    P_yaw=1.5,
                    K_dist=0.5,
                    stop_dist=0.1,
                    rate_hz=20.0,
                )
                print(vels(speed, turn))

            else:
                # any other key: stop
                x = y = z = th = 0.0
                if key == '\x03':  # Ctrl+C
                    break

            # Normal teleop command (when not in an autopilot routine)
            twist = Twist()
            twist.linear.x = x * speed
            twist.linear.y = y * speed
            twist.linear.z = 0.0
            twist.angular.x = 0.0
            twist.angular.y = 0.0
            twist.angular.z = th * turn
            pub.publish(twist)

    except Exception as e:
        print(e)

    finally:
        twist = Twist()
        pub.publish(twist)
        restoreTerminalSettings(settings)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()