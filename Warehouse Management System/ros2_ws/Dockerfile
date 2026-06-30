FROM osrf/ros:jazzy-desktop-full

RUN apt-get update && apt-get install -y \
    ros-jazzy-navigation2 \
    ros-jazzy-slam-toolbox \
    ros-jazzy-nav2-minimal-tb4-sim \
    ros-jazzy-nav2-minimal-tb4-description \
    ros-jazzy-diagnostic-updater \
    python3-paho-mqtt \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /ros2_ws
COPY src/ src/

RUN . /opt/ros/jazzy/setup.sh && \
    colcon build --packages-skip slam_toolbox

COPY entrypoint.sh /
ENTRYPOINT ["/entrypoint.sh"]
