#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
#  imu_serial_node.py  —  ROS 2 Jazzy | AURA Rover
#
#  IMU HARDWARE: MPU-6500 (InvenSense)
#    6-DOF: 3-axis accelerometer + 3-axis gyroscope
#    NO magnetometer — mx, my, mz are always 0.0
#    I2C address: 0x68  |  WHO_AM_I: 0x70
#
#  SERIAL PROTOCOL (Arduino side):
#    "IMU ax ay az gx gy gz 0 0 0\n"
#
#    ax, ay, az : linear acceleration  [m/s²]   (MPU-6500, ±2g,   16384 LSB/g)
#    gx, gy, gz : angular velocity     [rad/s]  (MPU-6500, ±250°/s, 131 LSB/°/s)
#    mx, my, mz : always 0.0  (no magnetometer)
#
#  IMPORTANT — NO COMPASS:
#    Without a magnetometer, imu_filter_madgwick runs in 6-DOF mode.
#    Absolute yaw will drift over time.  The EKF fuses only gyro angular
#    rate (vyaw), NOT absolute yaw orientation.  Wheel odometry provides
#    the primary heading reference.
#
#  ROS INTERFACE:
#    Publishes:  /imu/data_raw   [sensor_msgs/Imu]
#                /imu/mag        [sensor_msgs/MagneticField]   (µT → Tesla)
#
#  DOWNSTREAM:
#    imu_filter_madgwick subscribes /imu/data_raw + /imu/mag
#    and publishes /imu/data (with orientation quaternion).
#    robot_localization EKF subscribes /imu/data.
#
#  MPU9050 NOISE SPECIFICATIONS (datasheet, typical):
#    Accelerometer noise density : ±400 µg/√Hz  → σ ≈ 0.004 m/s² at 100 Hz BW
#    Gyroscope  noise density    : ±0.01 °/s/√Hz → σ ≈ 0.0017 rad/s at 100 Hz
#    Magnetometer noise          : ±0.6 µT (AK8963 companion compass)
#
# ═══════════════════════════════════════════════════════════════════════════════

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

import serial
import math
from sensor_msgs.msg import Imu, MagneticField


# ── Covariance matrices (row-major 3×3) ───────────────────────────────────────
# MPU-6500 datasheet noise figures:
#   Accel noise density : 300 µg/√Hz  → σ ≈ 0.003 m/s²   at 100 Hz BW
#   Gyro  noise density : 0.01 °/s/√Hz → σ ≈ 0.0017 rad/s at 100 Hz BW
#   Magnetometer        : NOT PRESENT  → always 0.0

ORIENTATION_COV = [
    -1.0, 0.0, 0.0,   # -1 signals EKF: orientation NOT provided here
     0.0, 0.0, 0.0,
     0.0, 0.0, 0.0,
]

# Gyro: σ = 0.0017 rad/s  → variance = 2.89×10⁻⁶ rad²/s²
ANGULAR_VEL_COV = [
    2.89e-6, 0.0,     0.0,
    0.0,     2.89e-6, 0.0,
    0.0,     0.0,     2.89e-6,
]

# Accel: σ = 0.003 m/s²  → variance = 9.0×10⁻⁶ m²/s⁴
LINEAR_ACCEL_COV = [
    9.0e-6, 0.0,    0.0,
    0.0,    9.0e-6, 0.0,
    0.0,    0.0,    9.0e-6,
]

# Magnetometer: MPU-6500 has NO magnetometer.
# Set a very large covariance so any consumer knows the data is unusable.
MAG_COV = [
    9.9e9, 0.0,   0.0,
    0.0,   9.9e9, 0.0,
    0.0,   0.0,   9.9e9,
]


class ImuSerialNode(Node):
    """
    Serial bridge for MPU-6500 (accel + gyro only) via Arduino Nano.

    MPU-6500 is a 6-DOF IMU — it has NO magnetometer.
    mx, my, mz in every IMU packet are always 0.0.
    imu_filter_madgwick must be configured with use_mag=False.
    The EKF fuses only gyro angular rate (vyaw), not absolute yaw.

    Reads IMU packets from serial port and publishes:
      /imu/data_raw  — accel + gyro (no orientation, no mag)
      /imu/mag       — published but all zeros (for topic compatibility)
    """

    def __init__(self):
        super().__init__('imu_serial_node')

        # ── Declare parameters ────────────────────────────────────────────────
        self.declare_parameter('serial_port',  '/dev/ttyUSB0')
        self.declare_parameter('serial_baud',  115200)
        self.declare_parameter('imu_frame_id', 'imu_link')

        port          = self.get_parameter('serial_port').value
        baud          = self.get_parameter('serial_baud').value
        self.frame_id = self.get_parameter('imu_frame_id').value

        # ── QoS ───────────────────────────────────────────────────────────────
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        # ── Publishers ────────────────────────────────────────────────────────
        self.imu_pub = self.create_publisher(Imu,           '/imu/data_raw', sensor_qos)
        self.mag_pub = self.create_publisher(MagneticField, '/imu/mag',      sensor_qos)

        # ── Serial port ───────────────────────────────────────────────────────
        try:
            self.ser = serial.Serial(port, baud, timeout=0.1)
            self.get_logger().info(
                f'[imu_serial_node] Serial port {port} @ {baud} baud opened'
            )
        except serial.SerialException as exc:
            self.get_logger().fatal(
                f'[imu_serial_node] Cannot open {port}: {exc}'
            )
            raise SystemExit(1)

        # ── Timer: poll at 100 Hz; actual publish rate depends on Arduino ─────
        self.create_timer(0.01, self._read_serial)

        self.get_logger().info(
            f'[imu_serial_node] Ready | frame_id={self.frame_id} | '
            f'Publishing /imu/data_raw and /imu/mag'
        )

    # ─────────────────────────────────────────────────────────────────────────
    def _read_serial(self):
        """Read one line from serial and dispatch to handler."""
        try:
            if self.ser.in_waiting == 0:
                return
            raw = self.ser.readline()
        except serial.SerialException as exc:
            self.get_logger().warning(f'Serial read error: {exc}')
            return

        try:
            line = raw.decode('ascii', errors='ignore').strip()
        except Exception:
            return

        if line.startswith('IMU '):
            self._handle_imu(line)

    # ─────────────────────────────────────────────────────────────────────────
    def _handle_imu(self, line: str):
        """
        Parse and publish IMU packet.

        Packet format: "IMU ax ay az gx gy gz mx my mz"
          ax, ay, az : acceleration [m/s²]
          gx, gy, gz : angular rate  [rad/s]
          mx, my, mz : magnetic field [µT]
        """
        parts = line.split()
        if len(parts) != 10:
            self.get_logger().debug(f'Malformed IMU packet ({len(parts)} tokens): {repr(line)}')
            return

        try:
            ax = float(parts[1]); ay = float(parts[2]); az = float(parts[3])
            gx = float(parts[4]); gy = float(parts[5]); gz = float(parts[6])
            mx = float(parts[7]); my = float(parts[8]); mz = float(parts[9])
        except ValueError:
            self.get_logger().debug(f'IMU parse error: {repr(line)}')
            return

        stamp = self.get_clock().now().to_msg()

        # ── Publish Imu ───────────────────────────────────────────────────────
        imu_msg = Imu()
        imu_msg.header.stamp    = stamp
        imu_msg.header.frame_id = self.frame_id

        # Orientation not available from raw IMU — signal with -1 in cov[0]
        imu_msg.orientation_covariance = ORIENTATION_COV

        imu_msg.angular_velocity.x = gx
        imu_msg.angular_velocity.y = gy
        imu_msg.angular_velocity.z = gz
        imu_msg.angular_velocity_covariance = ANGULAR_VEL_COV

        imu_msg.linear_acceleration.x = ax
        imu_msg.linear_acceleration.y = ay
        imu_msg.linear_acceleration.z = az
        imu_msg.linear_acceleration_covariance = LINEAR_ACCEL_COV

        self.imu_pub.publish(imu_msg)

        # ── Publish MagneticField (µT → Tesla: multiply by 1×10⁻⁶) ──────────
        mag_msg = MagneticField()
        mag_msg.header.stamp    = stamp
        mag_msg.header.frame_id = self.frame_id
        mag_msg.magnetic_field.x = mx * 1.0e-6
        mag_msg.magnetic_field.y = my * 1.0e-6
        mag_msg.magnetic_field.z = mz * 1.0e-6
        mag_msg.magnetic_field_covariance = MAG_COV

        self.mag_pub.publish(mag_msg)

    # ─────────────────────────────────────────────────────────────────────────
    def destroy_node(self):
        if hasattr(self, 'ser') and self.ser.is_open:
            self.ser.close()
        super().destroy_node()


# ─────────────────────────────────────────────────────────────────────────────
def main(args=None):
    rclpy.init(args=args)
    node = ImuSerialNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
