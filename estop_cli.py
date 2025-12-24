#!/usr/bin/env python3

"""
Terminal-based E-stop and safety filter for LIMO.

Use this when you are SSH'ed into the robot and cannot open a GUI window.

Behavior:
- Subscribes to raw velocity commands on `cmd_vel_raw`.
- Publishes safe velocity commands on `cmd_vel`.
- Publishes the E-stop state on `/estop` (std_msgs/Bool).

Keys (in the terminal where this script runs):
  s or SPACE : ACTIVATE E-stop (latch, send zero cmd_vel)
  c          : CLEAR E-stop (allow motion again)
  q or Ctrl+C: Quit (leaves E-stop ACTIVE as a conservative default)
"""

import sys
import select
import termios
import tty

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from std_msgs.msg import Bool


class EstopCliNode(Node):
    def __init__(self):
        super().__init__("limo_estop_cli")

        self.estop_active = False

        self.estop_pub = self.create_publisher(Bool, "/estop", 10)
        self.cmd_vel_pub = self.create_publisher(Twist, "cmd_vel", 10)
        self.cmd_vel_raw_sub = self.create_subscription(
            Twist, "cmd_vel_raw", self.cmd_vel_raw_callback, 10
        )

        self.get_logger().info(
            "LIMO E-stop CLI initialized. "
            "Keys: [s/SPACE]=STOP, [c]=CLEAR, [q/Ctrl+C]=quit."
        )

    # ---- ROS helpers ----

    def publish_estop_state(self):
        msg = Bool()
        msg.data = self.estop_active
        self.estop_pub.publish(msg)

    def publish_zero_cmd(self):
        self.cmd_vel_pub.publish(Twist())

    def cmd_vel_raw_callback(self, msg: Twist):
        """Filter raw velocity commands based on current E-stop state."""
        if self.estop_active:
            # Force zero command while stopped
            self.publish_zero_cmd()
        else:
            # Pass through original command
            self.cmd_vel_pub.publish(msg)

    # ---- E-stop control ----

    def activate_estop(self):
        if not self.estop_active:
            self.estop_active = True
            self.publish_estop_state()
            self.publish_zero_cmd()
            self.get_logger().warn("E-STOP ACTIVATED (CLI)")

    def clear_estop(self):
        if not self.estop_active:
            return
        self.estop_active = False
        self.publish_estop_state()
        self.get_logger().info("E-STOP CLEARED (CLI)")


def save_terminal_settings():
    return termios.tcgetattr(sys.stdin)


def restore_terminal_settings(settings):
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)


def main(args=None):
    rclpy.init(args=args)
    node = EstopCliNode()

    settings = save_terminal_settings()
    tty.setraw(sys.stdin.fileno())

    print("\n[E-STOP CLI]")
    print("  s / SPACE : ACTIVATE E-stop (latch, send zero cmd_vel)")
    print("  c         : CLEAR E-stop (allow motion again)")
    print("  q / Ctrl+C: Quit (leaves E-stop ACTIVE)\n")

    try:
        while rclpy.ok():
            # Spin ROS briefly (non-blocking)
            rclpy.spin_once(node, timeout_sec=0.0)

            # Check if a key is available, with short timeout
            rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
            if rlist:
                ch = sys.stdin.read(1)

                if ch in ("s", "S", " "):
                    node.activate_estop()
                elif ch in ("c", "C"):
                    node.clear_estop()
                elif ch in ("q", "Q", "\x03"):  # q or Ctrl+C
                    break

    except KeyboardInterrupt:
        pass
    finally:
        # On exit, enforce a safe state: E-stop active and zero cmd_vel
        node.estop_active = True
        node.publish_estop_state()
        node.publish_zero_cmd()
        restore_terminal_settings(settings)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()



