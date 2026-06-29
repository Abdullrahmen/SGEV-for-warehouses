#!/usr/bin/env python3
"""
ROS2 odom_node: converts LeftRPM / RightRPM from serial_node
into nav_msgs/Odometry and odom->base_footprint TF.

Fixes vs original version
──────────────────────────
1. Midpoint (RK2) integration  – theta is advanced at the half-step so that
   x/y are integrated with the correct heading. The old code used the
   post-update theta, introducing systematic error on any curved path.

2. RPM sync guard  – left and right RPM arrive on separate topics and can
   be arbitrarily out of phase. The timer now skips integration when the
   two latest samples are more than `rpm_sync_max_gap` seconds apart,
   preventing phantom motion from a stale half-update.

3. Linear velocity deadband  – when the robot spins in place, floating-point
   noise in v_left + v_right produces a tiny nonzero v that integrates into
   a growing circle in x/y.  Any |v| below `linear_deadband` is clamped to
   zero so position does not drift during pure rotation.

4. Angular velocity deadband  – symmetric guard for omega; prevents phantom
   heading drift when the robot is stationary.

5. theta wrapping  – atan2 normalisation keeps theta in (-π, π] and avoids
   floating-point accumulation on long runs.
"""

import math

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32
from nav_msgs.msg import Odometry
from geometry_msgs.msg import TransformStamped
import tf2_ros


class OdomNode(Node):
    def __init__(self):
        super().__init__('odom_node')

        # ── Robot geometry ─────────────────────────────────────────────── #
        self.declare_parameter('wheel_radius',      0.065)   # metres  ← measure!
        self.declare_parameter('wheel_base',        0.97)    # metres  ← measure!

        # ── Deadbands ──────────────────────────────────────────────────── #
        # Clamp |v| below this to zero → stops position drift during
        # spin-in-place.  Set to the smallest reliable linear speed your
        # encoders can distinguish (typically 1–5 mm/s).
        self.declare_parameter('linear_deadband',   0.001)   # m/s

        # Clamp |omega| below this to zero → stops heading drift when
        # stationary.  Typically 0.005–0.02 rad/s.
        self.declare_parameter('angular_deadband',  0.01)    # rad/s

        # ── Sync guard ─────────────────────────────────────────────────── #
        self.declare_parameter('rpm_sync_max_gap',  0.05)    # seconds

        # ── Covariance diagonal ────────────────────────────────────────── #
        self.declare_parameter('cov_x',   0.001)
        self.declare_parameter('cov_y',   0.001)
        self.declare_parameter('cov_yaw', 0.001)
        self.declare_parameter('cov_vx',  0.001)
        self.declare_parameter('cov_vy',  0.0001)
        self.declare_parameter('cov_wz',  0.001)

        self.wheel_radius      = self.get_parameter('wheel_radius').value
        self.wheel_base        = self.get_parameter('wheel_base').value
        self.linear_deadband   = self.get_parameter('linear_deadband').value
        self.angular_deadband  = self.get_parameter('angular_deadband').value
        self.rpm_sync_max_gap  = self.get_parameter('rpm_sync_max_gap').value

        self.cov_x   = self.get_parameter('cov_x').value
        self.cov_y   = self.get_parameter('cov_y').value
        self.cov_yaw = self.get_parameter('cov_yaw').value
        self.cov_vx  = self.get_parameter('cov_vx').value
        self.cov_vy  = self.get_parameter('cov_vy').value
        self.cov_wz  = self.get_parameter('cov_wz').value

        # ── State ──────────────────────────────────────────────────────── #
        self.x     = 0.0
        self.y     = 0.0
        self.theta = 0.0

        self.left_rpm       = 0.0
        self.right_rpm      = 0.0
        self.left_rpm_time  = None
        self.right_rpm_time = None

        self.last_time = self.get_clock().now()

        # ── ROS I/O ────────────────────────────────────────────────────── #
        self.create_subscription(Float32, 'left_rpm',  self._left_cb,  10)
        self.create_subscription(Float32, 'right_rpm', self._right_cb, 10)

        self.odom_pub       = self.create_publisher(Odometry, 'odom', 10)
        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)

        self.create_timer(0.02, self._update)   # 50 Hz

        self.get_logger().info(
            f'odom_node started | '
            f'wheel_radius={self.wheel_radius} m  '
            f'wheel_base={self.wheel_base} m  '
            f'linear_deadband={self.linear_deadband} m/s  '
            f'angular_deadband={self.angular_deadband} rad/s  '
            f'rpm_sync_max_gap={self.rpm_sync_max_gap} s'
        )

    # ── Callbacks ──────────────────────────────────────────────────────── #

    def _left_cb(self, msg: Float32):
        self.left_rpm      = msg.data
        self.left_rpm_time = self.get_clock().now()

    def _right_cb(self, msg: Float32):
        self.right_rpm      = msg.data
        self.right_rpm_time = self.get_clock().now()

    # ── 50 Hz integration loop ─────────────────────────────────────────── #

    def _update(self):
        now = self.get_clock().now()
        dt  = (now - self.last_time).nanoseconds * 1e-9
        self.last_time = now

        if dt <= 0.0:
            return

        # ── Sync guard ── #
        if self.rpm_sync_max_gap > 0.0:
            if self.left_rpm_time is None or self.right_rpm_time is None:
                return
            gap = abs(
                (self.left_rpm_time - self.right_rpm_time).nanoseconds
            ) * 1e-9
            if gap > self.rpm_sync_max_gap:
                self.get_logger().debug(
                    f'RPM sync gap {gap*1e3:.1f} ms > '
                    f'{self.rpm_sync_max_gap*1e3:.0f} ms — skipping'
                )
                return

        # ── Wheel velocities (m/s) ── #
        v_left  = (self.left_rpm  / 60.0) * (2.0 * math.pi * self.wheel_radius)
        v_right = (self.right_rpm / 60.0) * (2.0 * math.pi * self.wheel_radius)

        v     = (v_right + v_left)  / 2.0
        omega = (v_right - v_left)  / self.wheel_base

        # ── FIX 3 & 4: deadbands ──────────────────────────────────────── #
        # Clamp tiny velocities that are purely encoder / rounding noise.
        # This is the direct fix for the "odom circles during spin-in-place"
        # bug: when the robot rotates, v_left ≈ -v_right so v ≈ 0, but
        # floating-point residuals accumulate into a growing position error.
        if abs(v) <= self.linear_deadband:
            v = 0.0
        if abs(omega) <= self.angular_deadband:
            omega = 0.0

        # ── FIX 1: midpoint (RK2) integration ─────────────────────────── #
        theta_mid   = self.theta + 0.5 * omega * dt
        self.x     += v * math.cos(theta_mid) * dt
        self.y     += v * math.sin(theta_mid) * dt
        self.theta += omega * dt

        # Wrap theta to (-π, π] — FIX 5
        self.theta = math.atan2(math.sin(self.theta), math.cos(self.theta))

        # ── Quaternion (rotation about Z only) ── #
        qz = math.sin(self.theta / 2.0)
        qw = math.cos(self.theta / 2.0)

        stamp = now.to_msg()

        # ── Covariance matrices (6×6, row-major) ── #
        pose_cov = [0.0] * 36
        pose_cov[0]  = self.cov_x
        pose_cov[7]  = self.cov_y
        pose_cov[14] = 1e-9
        pose_cov[21] = 1e-9
        pose_cov[28] = 1e-9
        pose_cov[35] = self.cov_yaw

        twist_cov = [0.0] * 36
        twist_cov[0]  = self.cov_vx
        twist_cov[7]  = self.cov_vy
        twist_cov[14] = 1e-9
        twist_cov[21] = 1e-9
        twist_cov[28] = 1e-9
        twist_cov[35] = self.cov_wz

        # ── Publish /odom ── #
        odom = Odometry()
        odom.header.stamp    = stamp
        odom.header.frame_id = 'odom'
        odom.child_frame_id  = 'base_footprint'

        odom.pose.pose.position.x    = self.x
        odom.pose.pose.position.y    = self.y
        odom.pose.pose.orientation.z = qz
        odom.pose.pose.orientation.w = qw
        odom.pose.covariance         = pose_cov

        # Publish clamped velocities so downstream (e.g. EKF) sees clean data
        odom.twist.twist.linear.x  = v
        odom.twist.twist.angular.z = omega
        odom.twist.covariance      = twist_cov

        self.odom_pub.publish(odom)

        # ── Broadcast odom → base_footprint TF ── #
        tf = TransformStamped()
        tf.header.stamp    = stamp
        tf.header.frame_id = 'odom'
        tf.child_frame_id  = 'base_footprint'

        tf.transform.translation.x = self.x
        tf.transform.translation.y = self.y
        tf.transform.translation.z = 0.0
        tf.transform.rotation.z    = qz
        tf.transform.rotation.w    = qw

        self.tf_broadcaster.sendTransform(tf)

        self.get_logger().debug(
            f'x={self.x:.3f} y={self.y:.3f} '
            f'θ={math.degrees(self.theta):.1f}°  '
            f'v={v:.3f} m/s  ω={omega:.3f} rad/s'
        )


def main(args=None):
    rclpy.init(args=args)
    node = OdomNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
