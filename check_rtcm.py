#!/usr/bin/env python3
import serial
from datetime import datetime
import argparse

PORT = "/dev/tty.usbmodem1101"  # change if needed
BAUD = 115200                   # match what QGC used

ser = serial.Serial(PORT, BAUD, timeout=0.1)
buf = bytearray()

parser = argparse.ArgumentParser(description='Check RTCM3 messages from a serial port')
parser.add_argument('--debug', action='store_true', help='print debug information')
args = parser.parse_args()

print(f"[{datetime.now()}] Listening on {PORT} for RTCM3...")

def find_rtcm_messages(data_buf):
    """Yield (msg_type, length) for each complete RTCM3 message in data_buf.
       Returns also the leftover buffer."""
    i = 0
    n = len(data_buf)
    results = []

    while i + 6 <= n:  # need at least preamble + length + crc
        # search for 0xD3 preamble
        if data_buf[i] != 0xD3:
            i += 1
            continue

        if i + 3 > n:
            break  # not enough data for length yet

        length = ((data_buf[i+1] & 0x03) << 8) | data_buf[i+2]
        frame_len = 3 + length + 3  # header + payload + 3-byte CRC

        if i + frame_len > n:
            break  # wait for more bytes

        # RTCM3 message header starts after 3 bytes (preamble+length)
        header0 = data_buf[i+3]
        header1 = data_buf[i+4]
        # message number: first 12 bits of header
        msg_type = ((header0 << 4) | (header1 >> 4)) & 0x0FFF

        results.append((msg_type, length))

        # skip this whole frame
        i += frame_len

    # leftover bytes that might be start of next frame
    leftover = data_buf[i:]
    return results, leftover

try:
    while True:
        chunk = ser.read(4096)
        if chunk:
            if args.debug:
                print(f"chunk: {chunk}")
            buf.extend(chunk)
            msgs, buf = find_rtcm_messages(buf)
            for mt, ln in msgs:
                print(f"[{datetime.now().time()}] RTCM msg {mt} (len={ln})")
except KeyboardInterrupt:
    print("Stopping.")
finally:
    ser.close()

