#!/usr/bin/env python3
"""
ROS2 odom_node: converts LeftRPM / RightRPM from serial_node
into nav_msgs/Odometry and odom->base_link TF.
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32
from nav_msgs.msg import Odometry
from geometry_msgs.msg import TransformStamped
import tf2_ros
import math


class OdomNode(Node):
    def __init__(self):
        super().__init__('odom_node')

        self.declare_parameter('wheel_radius', 0.0325)
        self.declare_parameter('wheel_base',   0.23)

        self.wheel_radius = self.get_parameter('wheel_radius').value
        self.wheel_base   = self.get_parameter('wheel_base').value

        self.x     = 0.0
        self.y     = 0.0
        self.theta = 0.0

        self.left_rpm  = 0.0
        self.right_rpm = 0.0
        self.last_time = self.get_clock().now()

        # ── Covariance tuning parameters ── #
        # Increase these if odometry drifts faster than expected
        # Decrease if your encoder feedback is very accurate
        self.declare_parameter('cov_x',   0.001)   # x position variance (m²)
        self.declare_parameter('cov_y',   0.001)   # y position variance (m²)
        self.declare_parameter('cov_yaw', 0.001)   # yaw variance (rad²)
        self.declare_parameter('cov_vx',  0.001)   # linear velocity variance (m²/s²)
        self.declare_parameter('cov_vy',  0.0001)  # very small — robot can't move sideways
        self.declare_parameter('cov_wz',  0.001)   # angular velocity variance (rad²/s²)

        self.cov_x   = self.get_parameter('cov_x').value
        self.cov_y   = self.get_parameter('cov_y').value
        self.cov_yaw = self.get_parameter('cov_yaw').value
        self.cov_vx  = self.get_parameter('cov_vx').value
        self.cov_vy  = self.get_parameter('cov_vy').value
        self.cov_wz  = self.get_parameter('cov_wz').value

        self.create_subscription(Float32, 'left_rpm',  self._left_cb,  10)
        self.create_subscription(Float32, 'right_rpm', self._right_cb, 10)

        self.odom_pub = self.create_publisher(Odometry, 'odom', 10)
        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)

        self.create_timer(0.02, self._update)

        self.get_logger().info(
            f'odom_node started | '
            f'wheel_radius={self.wheel_radius}m  wheel_base={self.wheel_base}m'
        )

    def _left_cb(self, msg: Float32):
        self.left_rpm = msg.data

    def _right_cb(self, msg: Float32):
        self.right_rpm = msg.data

    def _update(self):
        now = self.get_clock().now()
        dt  = (now - self.last_time).nanoseconds * 1e-9
        self.last_time = now

        if dt <= 0.0:
            return

        v_left  = (self.left_rpm  / 60.0) * (2.0 * math.pi * self.wheel_radius)
        v_right = (self.right_rpm / 60.0) * (2.0 * math.pi * self.wheel_radius)

        v     = (v_right + v_left)  / 2.0
        omega = (v_right - v_left)  / self.wheel_base

        self.theta += omega * dt
        self.x     += v * math.cos(self.theta) * dt
        self.y     += v * math.sin(self.theta) * dt

        qz = math.sin(self.theta / 2.0)
        qw = math.cos(self.theta / 2.0)

        stamp = now.to_msg()

        # ── Build pose covariance (6x6 = 36 elements, row-major) ── #
        # Indices: x=0, y=7, z=14, roll=21, pitch=28, yaw=35
        # z, roll, pitch are fixed at 0 for ground robot → very small value (not zero to avoid singularity)
        pose_cov = [0.0] * 36
        pose_cov[0]  = self.cov_x      # x
        pose_cov[7]  = self.cov_y      # y
        pose_cov[14] = 1e-9            # z      (ground robot, no vertical motion)
        pose_cov[21] = 1e-9            # roll   (ground robot)
        pose_cov[28] = 1e-9            # pitch  (ground robot)
        pose_cov[35] = self.cov_yaw    # yaw

        # ── Build twist covariance (6x6 = 36 elements, row-major) ── #
        # vx=0, vy=7, vz=14, wx=21, wy=28, wz=35
        twist_cov = [0.0] * 36
        twist_cov[0]  = self.cov_vx    # linear x velocity
        twist_cov[7]  = self.cov_vy    # linear y velocity (near zero — no sideways slip modeled)
        twist_cov[14] = 1e-9           # linear z velocity
        twist_cov[21] = 1e-9           # angular x
        twist_cov[28] = 1e-9           # angular y
        twist_cov[35] = self.cov_wz    # angular z (yaw rate)

        # ── Publish /odom ── #
        odom = Odometry()
        odom.header.stamp    = stamp
        odom.header.frame_id = 'odom'
        odom.child_frame_id  = 'base_link'

        odom.pose.pose.position.x    = self.x
        odom.pose.pose.position.y    = self.y
        odom.pose.pose.orientation.z = qz
        odom.pose.pose.orientation.w = qw
        odom.pose.covariance         = pose_cov

        odom.twist.twist.linear.x  = v
        odom.twist.twist.angular.z = omega
        odom.twist.covariance      = twist_cov

        self.odom_pub.publish(odom)

        # ── Broadcast odom → base_link TF ── #
        tf = TransformStamped()
        tf.header.stamp    = stamp
        tf.header.frame_id = 'odom'
        tf.child_frame_id  = 'base_link'

        tf.transform.translation.x = self.x
        tf.transform.translation.y = self.y
        tf.transform.translation.z = 0.0
        tf.transform.rotation.z    = qz
        tf.transform.rotation.w    = qw

        self.tf_broadcaster.sendTransform(tf)

        self.get_logger().debug(
            f'x={self.x:.3f} y={self.y:.3f} θ={math.degrees(self.theta):.1f}°  '
            f'v={v:.3f}m/s  ω={omega:.3f}rad/s'
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