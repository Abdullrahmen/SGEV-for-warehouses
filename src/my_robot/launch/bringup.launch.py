from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource

from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

import os


def generate_launch_description():

    view_robot = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory('my_robot'),
                'launch',
                'view_robot.launch.py'
            )
        )
    )

    odom_node = Node(
        package='odom_node',
        executable='odom_node',
        name='odom_node',
        output='screen'
    )

    scan_remap = Node(
        package='scan_remap',
        executable='scan_remap',
        name='scan_remap',
        output='screen'
    )

    return LaunchDescription([
        view_robot,
        odom_node,
        scan_remap,
    ])
