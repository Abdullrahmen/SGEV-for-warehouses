import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    pkg_robot_sim = get_package_share_directory("robot_simulation")
    pkg_robot_desc = get_package_share_directory("robot_description")
    pkg_nav2_sim = get_package_share_directory("nav2_minimal_tb4_sim")

    world_path = os.path.join(pkg_robot_sim, "worlds", "warehouse.sdf")
    robot_sdf_path = os.path.join(pkg_robot_desc, "urdf", "turtlebot4.urdf.xacro")
    nav2_params = os.path.join(pkg_robot_sim, "config", "nav2_params.yaml")
    slam_config = os.path.join(pkg_robot_sim, "config", "slam_toolbox.yaml")

    headless_arg = DeclareLaunchArgument(
        "headless", default_value="True", description="Run Gazebo headless"
    )

    gazebo_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_nav2_sim, "launch", "simulation.launch.py")
        ),
        launch_arguments={
            "world": world_path,
            "use_rviz": "False",
            "headless": LaunchConfiguration("headless"),
            "use_simulator": "True",
            "robot_sdf": robot_sdf_path,
            "x_pose": "0.0",
            "y_pose": "0.0",
        }.items(),
    )

    slam = Node(
        package="slam_toolbox",
        executable="async_slam_toolbox_node",
        name="slam_toolbox",
        parameters=[slam_config],
        output="screen",
    )

    amcl = Node(
        package="nav2_amcl",
        executable="amcl",
        name="amcl",
        parameters=[nav2_params],
        output="screen",
    )

    planner = Node(
        package="nav2_planner",
        executable="planner_server",
        name="planner_server",
        parameters=[nav2_params],
        output="screen",
    )

    controller = Node(
        package="nav2_controller",
        executable="controller_server",
        name="controller_server",
        parameters=[nav2_params],
        output="screen",
    )

    bt_navigator = Node(
        package="nav2_bt_navigator",
        executable="bt_navigator",
        name="bt_navigator",
        parameters=[nav2_params],
        output="screen",
    )

    recoveries = Node(
        package="nav2_behaviors",
        executable="behavior_server",
        name="recoveries_server",
        parameters=[nav2_params],
        output="screen",
    )

    lifecycle_manager = Node(
        package="nav2_lifecycle_manager",
        executable="lifecycle_manager",
        name="lifecycle_manager",
        parameters=[nav2_params],
        output="screen",
    )

    depth_to_scan = Node(
        package="depthimage_to_laserscan",
        executable="depthimage_to_laserscan_node",
        name="depth_to_scan",
        output="screen",
        remappings=[
            ("depth", "/rgbd_camera/depth_image"),
            ("depth_camera_info", "/rgbd_camera/camera_info"),
        ],
    )

    camera_depth_tf = Node(
        package="tf2_ros",
        executable="static_transform_publisher",
        name="camera_depth_frame_tf",
        arguments=[
            "--x", "0", "--y", "0", "--z", "0",
            "--roll", "0", "--pitch", "0", "--yaw", "0",
            "--frame-id", "oakd_rgb_camera_optical_frame",
            "--child-frame-id", "camera_depth_frame",
        ],
    )

    odom_tf_bridge = ExecuteProcess(
        cmd=["python3", os.path.join(pkg_robot_sim, "scripts", "odom_to_tf_bridge.py")],
        output="screen",
    )

    bridge = Node(
        package="mqtt_bridge",
        executable="mqtt_bridge_node",
        parameters=[{"robot_id": "R1"}],
    )

    return LaunchDescription([
        headless_arg,
        gazebo_sim,
        depth_to_scan,
        camera_depth_tf,
        odom_tf_bridge,
        slam,
        amcl,
        planner,
        controller,
        bt_navigator,
        recoveries,
        lifecycle_manager,
        bridge,
    ])
