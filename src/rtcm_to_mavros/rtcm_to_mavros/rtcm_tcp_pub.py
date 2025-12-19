#!/usr/bin/env python3
import socket
import rclpy
from rclpy.node import Node
from mavros_msgs.msg import RTCM

class RTCMTcpPublisher(Node):
    def __init__(self):
        super().__init__('rtcm_tcp_publisher')

        self.declare_parameter('host', '10.0.0.42')
        self.declare_parameter('port', 2101)
        self.declare_parameter('chunk_size', 180)  # safe size for MAVLink GPS_RTCM_DATA fragmentation

        self.host = self.get_parameter('host').get_parameter_value().string_value
        self.port = self.get_parameter('port').get_parameter_value().integer_value
        self.chunk_size = self.get_parameter('chunk_size').get_parameter_value().integer_value

        self.pub = self.create_publisher(RTCM, '/pixhawk/gps_rtk/send_rtcm', 10)

        self.sock = None
        self.timer = self.create_timer(0.1, self._tick)

        self.get_logger().info(f"Connecting to RTCM TCP source {self.host}:{self.port}")

    def _connect(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5.0)
        self.sock.connect((self.host, self.port))
        self.sock.settimeout(1.0)
        self.get_logger().info("RTCM TCP connected")

    def _tick(self):
        try:
            if self.sock is None:
                self._connect()

            data = self.sock.recv(4096)
            if not data:
                raise RuntimeError("RTCM TCP: connection closed")

            # publish in small chunks
            for i in range(0, len(data), self.chunk_size):
                chunk = data[i:i+self.chunk_size]
                msg = RTCM()
                msg.data = list(chunk)  # uint8[]
                self.pub.publish(msg)

        except Exception as e:
            self.get_logger().warn(f"RTCM stream error: {e}. Reconnecting...")
            self.sock = None

def main():
    rclpy.init()
    node = RTCMTcpPublisher()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

