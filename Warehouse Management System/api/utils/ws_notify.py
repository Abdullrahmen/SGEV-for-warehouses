from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


def notify_robot_pose(robot_id, x, y, yaw):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)("dashboard", {
        "type": "robot_pose",
        "robot_id": robot_id,
        "x": x,
        "y": y,
        "yaw": yaw,
    })


def notify_robot_status(robot_id, system_status):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)("dashboard", {
        "type": "robot_status",
        "robot_id": robot_id,
        "system_status": system_status,
    })


def notify_robot_mode(robot_id, operational_mode, controlled_by=None):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)("dashboard", {
        "type": "robot_mode",
        "robot_id": robot_id,
        "operational_mode": operational_mode,
        "controlled_by": controlled_by,
    })


def notify_robot_mission(robot_id, status):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)("dashboard", {
        "type": "robot_mission",
        "robot_id": robot_id,
        "status": status,
    })


def notify_order_update(order_data):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)("dashboard", {
        "type": "order_update",
        "order": order_data,
    })


def notify_map_preview(robot_id, image_base64):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)("dashboard", {
        "type": "map_preview",
        "robot_id": robot_id,
        "image_base64": image_base64,
    })
