#!/usr/bin/env python3

import threading

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from std_msgs.msg import Bool

import tkinter as tk
from tkinter import messagebox


class EstopGuiNode(Node):
    """
    Simple E-stop GUI and safety filter for LIMO:

    - Subscribes to raw velocity commands on `cmd_vel_raw`.
    - Publishes safe velocity commands on `cmd_vel`.
    - Provides a small window with:
        - A big red STOP button (and Space hot-key) to latch E-stop.
        - A CLEAR button (and 'c' key) to clear E-stop when safe.
    - Also publishes the E-stop state on `/estop` (std_msgs/Bool) for other nodes.

    Behavior:
    - When E-stop is INACTIVE: forward `cmd_vel_raw` to `cmd_vel`.
    - When E-stop is ACTIVE: publish zero Twist on `cmd_vel`
      regardless of incoming `cmd_vel_raw`.
    """

    def __init__(self):
        super().__init__("limo_estop_gui")

        # --- ROS interfaces ---
        self.estop_active = False

        self.estop_pub = self.create_publisher(Bool, "/estop", 10)
        self.cmd_vel_pub = self.create_publisher(Twist, "cmd_vel", 10)
        self.cmd_vel_raw_sub = self.create_subscription(
            Twist, "cmd_vel_raw", self.cmd_vel_raw_callback, 10
        )

        # --- GUI setup ---
        self.root = tk.Tk()
        self.root.title("LIMO E-STOP")

        self.root.geometry("320x220")
        self.root.resizable(False, False)

        self.status_label = tk.Label(
            self.root,
            text="E-STOP INACTIVE",
            font=("Helvetica", 16, "bold"),
            fg="green",
        )
        self.status_label.pack(pady=10)

        self.stop_button = tk.Button(
            self.root,
            text="STOP (SPACE)",
            font=("Helvetica", 18, "bold"),
            bg="red",
            fg="white",
            width=15,
            command=self.activate_estop,
        )
        self.stop_button.pack(pady=5)

        self.clear_button = tk.Button(
            self.root,
            text="CLEAR (c)",
            font=("Helvetica", 14),
            bg="grey",
            fg="black",
            width=12,
            command=self.clear_estop,
        )
        self.clear_button.pack(pady=5)

        # Keyboard bindings: Space = STOP, c = CLEAR, Esc / window close = close app
        self.root.bind("<space>", lambda event: self.activate_estop())
        self.root.bind("<Key-c>", lambda event: self.clear_estop())
        self.root.bind("<Escape>", lambda event: self.on_close())
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.get_logger().info(
            "LIMO E-stop GUI initialized. "
            "STOP: button or Space, CLEAR: button or 'c'."
        )

    # --------- ROS helpers ---------

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

    # --------- E-stop control ---------

    def activate_estop(self):
        if not self.estop_active:
            self.estop_active = True
            self.publish_estop_state()
            # Immediately send a zero command to stop the robot
            self.publish_zero_cmd()
            self.update_ui()
            self.get_logger().warn("E-STOP ACTIVATED via GUI")

    def clear_estop(self):
        if not self.estop_active:
            return

        # Simple confirmation dialog before clearing
        if not messagebox.askyesno(
            "Clear E-STOP",
            "Are you sure it is safe to clear the E-stop and allow motion?",
        ):
            return

        self.estop_active = False
        self.publish_estop_state()
        self.update_ui()
        self.get_logger().info("E-STOP CLEARED via GUI")

    # --------- UI helpers ---------

    def update_ui(self):
        if self.estop_active:
            self.status_label.config(text="E-STOP ACTIVE", fg="red")
            self.stop_button.config(bg="dark red", state="disabled")
            self.clear_button.config(bg="orange", state="normal")
        else:
            self.status_label.config(text="E-STOP INACTIVE", fg="green")
            self.stop_button.config(bg="red", state="normal")
            self.clear_button.config(bg="grey", state="normal")

    def on_close(self):
        """
        When the window closes, force a safe state:
        - Latch E-stop active.
        - Publish zero velocity once.
        Then destroy the window so mainloop() can exit.
        """
        self.estop_active = True
        self.publish_estop_state()
        self.publish_zero_cmd()
        self.get_logger().warn("E-STOP GUI closing, forcing E-STOP ACTIVE and zero cmd_vel")
        self.root.destroy()


def ros_spin(node: Node):
    """Spin ROS2 in a background thread so Tkinter mainloop can run in the main thread."""
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


def main(args=None):
    rclpy.init(args=args)
    node = EstopGuiNode()

    # Spin ROS2 in a background thread
    ros_thread = threading.Thread(target=ros_spin, args=(node,), daemon=True)
    ros_thread.start()

    # Run Tkinter GUI in the main thread
    try:
        node.root.mainloop()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()



