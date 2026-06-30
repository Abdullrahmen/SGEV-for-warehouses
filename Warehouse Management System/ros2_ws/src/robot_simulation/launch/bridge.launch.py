from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package="mqtt_bridge",
            executable="mqtt_bridge_node",
            parameters=[{"robot_id": "R1"}],
        ),
    ])
