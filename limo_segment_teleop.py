#!/usr/bin/env python3
import sys
import math
import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry

if sys.platform == 'win32':
    import msvcrt
else:
    import termios
    import tty


msg = """
Segment Teleop for LIMO (with yaw-hold)
---------------------------------------
Normal driving (same as teleop_twist_keyboard):

   u    i    o
   j    k    l
   m    ,    .

For Holonomic mode (strafing), hold down the shift key:
   U    I    O
   J    K    L
   M    <    >

t : up (+z)
b : down (-z)

Segment command (uses /wheel/odom yaw-hold):

   g : go forward 1.0 m with yaw-hold, then stop

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
    't': (0, 0, 1, 0),
    'b': (0, 0, -1, 0),
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
    return 'currently:\tspeed %s\tturn %s ' % (speed, turn)


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


class OdomWatcher(Node):
    def __init__(self):
        super().__init__('segment_teleop_odom_watcher')
        self.sub = self.create_subscription(
            Odometry,
            '/wheel/odom',
            self.odom_callback,
            10
        )
        self.last_x = None
        self.last_y = None
        self.last_yaw = None

    def odom_callback(self, msg: Odometry):
        self.last_x = msg.pose.pose.position.x
        self.last_y = msg.pose.pose.position.y
        self.last_yaw = quat_to_yaw_z(msg.pose.pose.orientation)


def run_segment_forward_yaw_hold(
    node: OdomWatcher,
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
      - apply yaw-hold: omega = -P * yaw_err, saturated
    """
    logger = node.get_logger()

    logger.info("Waiting for /wheel/odom...")
    while rclpy.ok() and (node.last_x is None or node.last_y is None or node.last_yaw is None):
        rclpy.spin_once(node, timeout_sec=0.1)

    if node.last_x is None:
        logger.warn("No odom received; aborting segment.")
        return

    start_x = node.last_x
    start_y = node.last_y
    yaw_ref = node.last_yaw
    logger.info(
        f"Starting forward segment: distance={distance:.2f} m, speed={speed:.2f} m/s, yaw_ref={math.degrees(yaw_ref):.1f}°"
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

        yaw_err_diff = (prev_yaw_err - yaw_err)/dt

        prev_yaw_err = yaw_err

        omega = -P * yaw_err -D * yaw_err_diff
        # saturate angular velocity
        if omega > max_omega:
            omega = max_omega
        elif omega < -max_omega:
            omega = -max_omega

        twist = Twist()
        twist.linear.x = abs(speed)   # forward
        twist.angular.z = omega
        pub.publish(twist)

        time.sleep(dt)

    # Stop at the end of the segment
    twist = Twist()
    pub.publish(twist)
    logger.info("Segment finished; robot stopped.")

    return prev_yaw_err


def main():
    settings = saveTerminalSettings()
    rclpy.init()

    node = OdomWatcher()
    pub = node.create_publisher(Twist, 'cmd_vel', 10)

    speed = 0.3   # default forward speed
    turn = 1.0
    x = y = z = th = 0.0
    status = 0
    prev_yaw_err = 0.0

    try:
        print(msg)
        print(vels(speed, turn))
        while True:
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
                # yaw-hold segment
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

            else:
                # any other key: stop
                x = y = z = th = 0.0
                if key == '\x03':  # Ctrl+C
                    break

            # Normal teleop command (when not in 'g' segment)
            twist = Twist()
            twist.linear.x = x * speed
            twist.linear.y = y * speed
            twist.linear.z = z * speed
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
