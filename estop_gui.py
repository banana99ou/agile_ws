#!/usr/bin/env python3

import threading

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from std_msgs.msg import Bool
from std_srvs.srv import SetBool, Trigger

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

    External interface (for other nodes/clients):
    - `/estop/set` (std_srvs/SetBool):
      - `data=True`  => ACTIVATE E-stop
      - `data=False` => CLEAR E-stop (only if parameter `allow_remote_clear:=true`)
    - `/estop/activate` (std_srvs/Trigger): ACTIVATE E-stop
    - `/estop/clear` (std_srvs/Trigger): CLEAR E-stop (only if `allow_remote_clear:=true`)
    - `/estop_cmd` (std_msgs/Bool topic): True=ACTIVATE, False=CLEAR (only if `allow_remote_clear:=true`)

    Behavior:
    - When E-stop is INACTIVE: forward `cmd_vel_raw` to `cmd_vel`.
    - When E-stop is ACTIVE: publish zero Twist on `cmd_vel`
      regardless of incoming `cmd_vel_raw`.
    """

    def __init__(self):
        super().__init__("limo_estop_gui")

        # --- ROS interfaces ---
        self.estop_active = False
        self.allow_remote_clear = (
            self.declare_parameter("allow_remote_clear", False).value
        )

        self.estop_pub = self.create_publisher(Bool, "/estop", 10)
        self.estop_cmd_sub = self.create_subscription(
            Bool, "/estop_cmd", self.estop_cmd_callback, 10
        )
        self.cmd_vel_pub = self.create_publisher(Twist, "cmd_vel", 10)
        self.cmd_vel_raw_sub = self.create_subscription(
            Twist, "cmd_vel_raw", self.cmd_vel_raw_callback, 10
        )

        # External interfaces (for other nodes/clients)
        # - /estop/set (std_srvs/SetBool): data=True -> ACTIVATE, data=False -> CLEAR (optional)
        # - /estop/activate (std_srvs/Trigger): ACTIVATE
        # - /estop/clear (std_srvs/Trigger): CLEAR (optional)
        self.estop_set_srv = self.create_service(SetBool, "/estop/set", self.on_estop_set)
        self.estop_activate_srv = self.create_service(
            Trigger, "/estop/activate", self.on_estop_activate
        )
        self.estop_clear_srv = self.create_service(
            Trigger, "/estop/clear", self.on_estop_clear
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
        self.get_logger().info(
            "External E-stop interface: /estop (state), /estop/set (service), /estop_cmd (topic). "
            f"Remote clear allowed: {self.allow_remote_clear}"
        )
        self.publish_estop_state()

    # --------- ROS helpers ---------

    def publish_estop_state(self):
        msg = Bool()
        msg.data = self.estop_active
        self.estop_pub.publish(msg)

    def publish_zero_cmd(self):
        self.cmd_vel_pub.publish(Twist())

    def estop_cmd_callback(self, msg: Bool):
        """
        External command topic callback.

        Topic: /estop_cmd (std_msgs/Bool)
        - True  => activate E-stop
        - False => clear E-stop (only if allow_remote_clear=True)
        """
        if msg.data:
            self.activate_estop(source="topic:/estop_cmd")
        else:
            if self.allow_remote_clear:
                self.clear_estop(source="topic:/estop_cmd", confirm=False)
            else:
                self.get_logger().warn(
                    "Ignoring remote CLEAR via /estop_cmd (allow_remote_clear=false)"
                )

    def cmd_vel_raw_callback(self, msg: Twist):
        """Filter raw velocity commands based on current E-stop state."""
        if self.estop_active:
            # Force zero command while stopped
            self.publish_zero_cmd()
        else:
            # Pass through original command
            self.cmd_vel_pub.publish(msg)

    # --------- E-stop control ---------

    def activate_estop(self, source: str = "local"):
        if not self.estop_active:
            self.estop_active = True
            self.publish_estop_state()
            # Immediately send a zero command to stop the robot
            self.publish_zero_cmd()
            self.update_ui()
            self.get_logger().warn(f"E-STOP ACTIVATED via GUI source={source}")

    def clear_estop(self, source: str = "local", confirm: bool = True):
        if not self.estop_active:
            return

        # Simple confirmation dialog before clearing
        if confirm:
            if not messagebox.askyesno(
                "Clear E-STOP",
                "Are you sure it is safe to clear the E-stop and allow motion?",
            ):
                return

        self.estop_active = False
        self.publish_estop_state()
        self.update_ui()
        self.get_logger().info(f"E-STOP CLEARED via GUI source={source}")

    # ---- External service handlers ----

    def on_estop_set(self, request: SetBool.Request, response: SetBool.Response):
        if request.data:
            self.activate_estop(source="service:/estop/set")
            response.success = True
            response.message = "E-stop ACTIVATED"
            return response

        # request.data == False => clear request
        if not self.allow_remote_clear:
            response.success = False
            response.message = "Remote CLEAR disabled (allow_remote_clear=false)"
            return response

        self.clear_estop(source="service:/estop/set", confirm=False)
        response.success = True
        response.message = "E-stop CLEARED"
        return response

    def on_estop_activate(self, request: Trigger.Request, response: Trigger.Response):
        self.activate_estop(source="service:/estop/activate")
        response.success = True
        response.message = "E-stop ACTIVATED"
        return response

    def on_estop_clear(self, request: Trigger.Request, response: Trigger.Response):
        if not self.allow_remote_clear:
            response.success = False
            response.message = "Remote CLEAR disabled (allow_remote_clear=false)"
            return response
        self.clear_estop(source="service:/estop/clear", confirm=False)
        response.success = True
        response.message = "E-stop CLEARED"
        return response

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



