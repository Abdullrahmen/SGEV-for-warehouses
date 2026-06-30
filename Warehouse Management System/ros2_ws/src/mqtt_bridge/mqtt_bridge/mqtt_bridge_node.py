import json
import base64
import io
import logging
import math
import os
import threading
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid, Odometry
from geometry_msgs.msg import Twist
from nav2_msgs.action import NavigateToPose
from slam_toolbox.srv import Reset
import paho.mqtt.client as mqtt

logger = logging.getLogger("mqtt_bridge")


class MQTTRos2Bridge(Node):
    def __init__(self):
        super().__init__("mqtt_bridge")

        self.declare_parameter("robot_id", "R1")
        self.declare_parameter("mqtt_host", "localhost")
        self.declare_parameter("mqtt_port", 1883)
        self.declare_parameter("mqtt_username", "robot_user")
        self.declare_parameter("mqtt_password", "robot_password")
        self.declare_parameter("map_topic", "/map")
        self.declare_parameter("pose_topic", "/odom")
        self.declare_parameter("cmd_vel_topic", "/cmd_vel")

        self.robot_id = self.get_parameter("robot_id").value
        self.mqtt_host = os.environ.get("MQTT_HOST", self.get_parameter("mqtt_host").value)
        self.mqtt_port = int(os.environ.get("MQTT_PORT", self.get_parameter("mqtt_port").value))

        self.mqtt_client = mqtt.Client(client_id=f"ros_bridge_{self.robot_id}")
        self.mqtt_client.username_pw_set(
            self.get_parameter("mqtt_username").value,
            self.get_parameter("mqtt_password").value,
        )
        self.mqtt_client.will_set(
            f"warehouse/robots/{self.robot_id}/system_status",
            "OFFLINE",
            qos=1,
            retain=True,
        )
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_message = self._on_mqtt_message
        self.mqtt_client.reconnect_delay_set(min_delay=1, max_delay=60)

        self._manual_cmd_pub = self.create_publisher(
            Twist, self.get_parameter("cmd_vel_topic").value, 10
        )

        self._nav_client = ActionClient(self, NavigateToPose, "navigate_to_pose")

        self._slam_reset_client = self.create_client(Reset, "/slam_toolbox/reset")

        self._map_sub = self.create_subscription(
            OccupancyGrid,
            self.get_parameter("map_topic").value,
            self._map_callback,
            10,
        )
        self._pose_sub = self.create_subscription(
            Odometry,
            self.get_parameter("pose_topic").value,
            self._pose_callback,
            10,
        )

        self._navigating = False
        self._current_waypoints = []
        self._waypoint_index = 0
        self._nav_goal_handle = None
        self._manual_vel_x = 0.0
        self._manual_vel_theta = 0.0
        self._manual_timer = None
        self._mapping = False
        self._latest_map = None
        self._current_pose = None
        self._auto_explore = False
        self._auto_spinning = False
        self._auto_spin_timer = None
        self._auto_angle = 0.0
        self._auto_waypoint_count = 0
        self._auto_max_waypoints = 24
        self._auto_consecutive_failures = 0

        self._connect_mqtt()

    def _connect_mqtt(self):
        try:
            self.mqtt_client.connect(self.mqtt_host, self.mqtt_port)
            self.mqtt_client.loop_start()
        except Exception as e:
            self.get_logger().error(f"MQTT connection failed: {e}")

    def _publish_online(self):
        self.mqtt_client.publish(
            f"warehouse/robots/{self.robot_id}/system_status",
            "ONLINE",
            qos=1,
            retain=True,
        )

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        self.get_logger().info(f"MQTT connected: {rc}")
        client.publish(
            f"warehouse/robots/{self.robot_id}/system_status",
            "ONLINE",
            qos=1,
            retain=True,
        )
        client.subscribe(f"warehouse/robots/{self.robot_id}/cmd_auto", qos=1)
        client.subscribe(f"warehouse/robots/{self.robot_id}/cmd_manual", qos=0)
        client.subscribe(f"warehouse/robots/{self.robot_id}/cmd_mapping", qos=1)

    def _on_mqtt_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode()
        if "cmd_auto" in topic:
            self._handle_cmd_auto(payload)
        elif "cmd_manual" in topic:
            self._handle_cmd_manual(payload)
        elif "cmd_mapping" in topic:
            self._handle_cmd_mapping(payload)

    def _handle_cmd_auto(self, payload):
        data = json.loads(payload)
        action = data.get("action")
        if action == "CANCEL":
            self._cancel_navigation()
        elif action == "NAVIGATE":
            waypoints = data.get("waypoints", [])
            self._start_navigation(waypoints)

    def _handle_cmd_manual(self, payload):
        command = payload.strip().upper()
        if command == "STOP":
            self._manual_vel_x = 0.0
            self._manual_vel_theta = 0.0
            self._stop_manual()
        elif command == "W":
            self._manual_vel_x = 0.5
            self._manual_vel_theta = 0.0
            self._start_manual()
        elif command == "S":
            self._manual_vel_x = -0.5
            self._manual_vel_theta = 0.0
            self._start_manual()
        elif command == "A":
            self._manual_vel_x = 0.0
            self._manual_vel_theta = 0.5
            self._start_manual()
        elif command == "D":
            self._manual_vel_x = 0.0
            self._manual_vel_theta = -0.5
            self._start_manual()

    def _handle_cmd_mapping(self, payload):
        data = json.loads(payload)
        action = data.get("action")
        if action == "START_MANUAL":
            self._mapping = True
            self._auto_explore = False
            self.get_logger().info("Started manual mapping")
        elif action == "START_AUTO":
            self._mapping = True
            self._auto_explore = True
            self._auto_spinning = True
            self._auto_angle = 0.0
            self._auto_waypoint_count = 0
            self._auto_consecutive_failures = 0
            self._current_pose = None
            self._reset_slam_map()
            self.get_logger().info("Started autonomous mapping (spinning to build initial map)")
            self._start_spin_for_map()
        elif action == "CANCEL":
            self._mapping = False
            self._auto_explore = False
            self._latest_map = None
            self._cancel_navigation()
            self._stop_spin_if_running()
            self._reset_slam_map()
            self.get_logger().info("Mapping cancelled")
        elif action == "STOP_AND_SAVE":
            self._mapping = False
            self._auto_explore = False
            self._stop_spin_if_running()
            self._cancel_navigation()
            map_name = data.get("map_name", "Scanned Map")
            self._publish_map_complete(map_name)

    def _reset_slam_map(self):
        if not self._slam_reset_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().warning("Slam_toolbox reset service not available")
            return
        req = Reset.Request()
        req.pause_new_measurements = False
        future = self._slam_reset_client.call_async(req)
        future.add_done_callback(lambda f: self.get_logger().info(
            "Slam_toolbox map reset" if f.result().result == 0 else "Slam_toolbox reset failed"
        ))

    def _start_navigation(self, waypoints):
        self._cancel_navigation()
        self._current_waypoints = waypoints
        self._waypoint_index = 0
        self._navigating = True
        self._send_nav_goal()

    def _send_nav_goal(self):
        if self._waypoint_index >= len(self._current_waypoints):
            self._navigating = False
            self.mqtt_client.publish(
                f"warehouse/robots/{self.robot_id}/mission_status",
                "COMPLETED",
                qos=1,
            )
            return

        if not self._nav_client.wait_for_server(timeout_sec=2.0):
            self.get_logger().error("Nav2 action server not available")
            self.mqtt_client.publish(
                f"warehouse/robots/{self.robot_id}/mission_status",
                "FAILED",
                qos=1,
            )
            self._navigating = False
            return

        wp = self._current_waypoints[self._waypoint_index]
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose.header.frame_id = "map"
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = wp["x"]
        goal_msg.pose.pose.position.y = wp["y"]
        goal_msg.pose.pose.orientation.w = 1.0

        self.get_logger().info(
            f"Sending Nav2 goal {self._waypoint_index + 1}/{len(self._current_waypoints)}: "
            f"({wp['x']:.2f}, {wp['y']:.2f})"
        )

        send_goal_future = self._nav_client.send_goal_async(
            goal_msg,
            feedback_callback=self._nav_feedback_callback
        )
        send_goal_future.add_done_callback(self._nav_goal_response_callback)

    def _nav_goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warning("Nav2 goal rejected")
            self.mqtt_client.publish(
                f"warehouse/robots/{self.robot_id}/mission_status",
                "FAILED",
                qos=1,
            )
            self._navigating = False
            return

        self._nav_goal_handle = goal_handle
        self.get_logger().info("Nav2 goal accepted")

        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._nav_result_callback)

    def _nav_feedback_callback(self, feedback_msg):
        pass

    def _nav_result_callback(self, future):
        result = future.result()
        self._navigating = False
        if result.status == 4:  # SUCCEEDED
            self.get_logger().info(f"Waypoint {self._waypoint_index + 1} reached")
            self._waypoint_index += 1
            self._auto_consecutive_failures = 0
            if self._auto_explore:
                self._send_auto_waypoint()
            else:
                self._send_nav_goal()
        else:
            self.get_logger().error(f"Nav2 failed with status {result.status}")
            if self._auto_explore:
                self._auto_consecutive_failures += 1
                if self._auto_consecutive_failures >= 5:
                    self.get_logger().info("Auto explore: too many consecutive failures, saving map")
                    self._auto_explore = False
                    self._mapping = False
                    self._publish_map_complete("Auto Scanned Map")
                else:
                    self.get_logger().info("Auto explore sending next waypoint after failure")
                    self._send_auto_waypoint()

    def _start_spin_for_map(self):
        twist = Twist()
        twist.angular.z = 0.5
        self._manual_cmd_pub.publish(twist)
        self._auto_spin_timer = self.create_timer(13.0, self._stop_spin_for_map)
        self.get_logger().info("Spinning 360° to build SLAM map")

    def _stop_spin_if_running(self):
        if self._auto_spin_timer:
            self._auto_spin_timer.cancel()
            self._auto_spin_timer = None
        if self._auto_spinning:
            self._auto_spinning = False
            twist = Twist()
            self._manual_cmd_pub.publish(twist)

    def _stop_spin_for_map(self):
        if self._auto_spin_timer:
            self._auto_spin_timer.cancel()
            self._auto_spin_timer = None
        self._auto_spinning = False
        twist = Twist()
        self._manual_cmd_pub.publish(twist)
        self.get_logger().info("Spin complete, starting auto waypoints")
        self._send_auto_waypoint()

    def _send_auto_waypoint(self):
        if not self._mapping or not self._auto_explore:
            return
        self._auto_waypoint_count += 1
        if self._auto_waypoint_count > self._auto_max_waypoints:
            self.get_logger().info(f"Auto explore completed {self._auto_max_waypoints} waypoints, saving map")
            self._auto_explore = False
            self._mapping = False
            self._cancel_navigation()
            self._publish_map_complete("Auto Scanned Map")
            return
        if not self._current_pose:
            self.get_logger().warning("No pose data yet, retrying in 3s")
            self.create_timer(3.0, lambda: self._retry_auto_waypoint())
            return
        STEP = 2.0
        x = self._current_pose["x"] + STEP * math.cos(self._auto_angle)
        y = self._current_pose["y"] + STEP * math.sin(self._auto_angle)
        waypoint = [{"x": round(x, 2), "y": round(y, 2)}]
        self._auto_angle += math.radians(60)
        self.get_logger().info(
            f"Auto explore: navigating to ({waypoint[0]['x']:.2f}, {waypoint[0]['y']:.2f})"
        )
        self._start_navigation(waypoint)

    def _retry_auto_waypoint(self):
        self._send_auto_waypoint()

    def _cancel_navigation(self):
        self._navigating = False
        self._current_waypoints = []
        self._waypoint_index = 0
        if self._nav_goal_handle:
            self._nav_goal_handle.cancel_goal_async()
            self._nav_goal_handle = None
        twist = Twist()
        self._manual_cmd_pub.publish(twist)

    def _start_manual(self):
        if self._manual_timer:
            return
        self._manual_timer = self.create_timer(0.1, self._publish_manual_vel)

    def _stop_manual(self):
        if self._manual_timer:
            self._manual_timer.cancel()
            self._manual_timer = None
        twist = Twist()
        self._manual_cmd_pub.publish(twist)

    def _publish_manual_vel(self):
        twist = Twist()
        twist.linear.x = self._manual_vel_x
        twist.angular.z = self._manual_vel_theta
        self._manual_cmd_pub.publish(twist)

    def _map_callback(self, msg):
        self._latest_map = msg
        if self._mapping:
            self._publish_map_preview(msg)

    def _pose_callback(self, msg):
        x = msg.pose.pose.position.x
        y = msg.pose.pose.position.y
        _, _, yaw = self._quaternion_to_euler(msg.pose.pose.orientation)
        self._current_pose = {"x": x, "y": y, "yaw": yaw}
        self.mqtt_client.publish(
            f"warehouse/robots/{self.robot_id}/pose",
            json.dumps({"x": x, "y": y, "yaw": yaw}),
            qos=0,
        )

    def _publish_map_preview(self, grid):
        width = grid.info.width
        height = grid.info.height
        try:
            img_bytes = bytearray(width * height)
            for i, val in enumerate(grid.data):
                if val == -1:
                    img_bytes[i] = 128
                elif val == 0:
                    img_bytes[i] = 255
                else:
                    img_bytes[i] = 0
            import numpy as np
            from PIL import Image
            arr = np.array(img_bytes, dtype=np.uint8).reshape((height, width))
            img = Image.fromarray(arr, mode="L")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            self.mqtt_client.publish(
                f"warehouse/robots/{self.robot_id}/map_preview",
                b64,
                qos=0,
            )
        except ImportError:
            self.get_logger().error("numpy or PIL not available for map preview")
        except Exception as e:
            self.get_logger().error(f"Map preview error: {e}")

    def _publish_map_complete(self, map_name):
        if not self._latest_map:
            self.get_logger().error("No map data to save")
            return
        grid = self._latest_map
        width = grid.info.width
        height = grid.info.height
        img_bytes = bytearray(width * height)
        for i, val in enumerate(grid.data):
            if val == -1:
                img_bytes[i] = 128
            elif val == 0:
                img_bytes[i] = 255
            else:
                img_bytes[i] = 0
        import numpy as np
        from PIL import Image
        arr = np.array(img_bytes, dtype=np.uint8).reshape((height, width))
        img = Image.fromarray(arr, mode="L")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        payload = json.dumps({
            "map_name": map_name,
            "map_image_base64": b64,
            "resolution": grid.info.resolution,
            "origin_x": grid.info.origin.position.x,
            "origin_y": grid.info.origin.position.y,
            "width_meters": width * grid.info.resolution,
            "height_meters": height * grid.info.resolution,
        })
        self.mqtt_client.publish(
            f"warehouse/robots/{self.robot_id}/map_complete",
            payload,
            qos=1,
        )

    def _quaternion_to_euler(self, q):
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        yaw = math.atan2(siny_cosp, cosy_cosp)
        return 0.0, 0.0, yaw

    def destroy_node(self):
        self.mqtt_client.disconnect()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = MQTTRos2Bridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
