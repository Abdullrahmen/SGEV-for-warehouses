import json
import logging
from asgiref.sync import async_to_sync
from channels.generic.websocket import JsonWebsocketConsumer
from rest_framework.authtoken.models import Token
from api.models import Robot
from api.utils.mqtt_publisher import MQTTPublisher

logger = logging.getLogger("api")


class DashboardConsumer(JsonWebsocketConsumer):
    def connect(self):
        token_key = self.scope["query_string"].decode().replace("token=", "")
        if not token_key:
            self.close(code=4001)
            return
        try:
            token = Token.objects.get(key=token_key)
            self.scope["user"] = token.user
        except Token.DoesNotExist:
            self.close(code=4001)
            return
        async_to_sync(self.channel_layer.group_add)("dashboard", self.channel_name)
        self.accept()
        logger.info(f"WebSocket connected: {token.user.username}")

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)("dashboard", self.channel_name)

    def receive_json(self, content):
        msg_type = content.get("type")
        if msg_type == "cmd_manual":
            self.handle_cmd_manual(content)

    def handle_cmd_manual(self, content):
        robot_id = content.get("robot_id")
        command = content.get("command")
        user = self.scope["user"]
        try:
            robot = Robot.objects.get(robot_id=robot_id)
        except Robot.DoesNotExist:
            self.send_json({"type": "error", "message": "Robot not found"})
            return
        if robot.controlled_by != user:
            self.send_json({"type": "error", "message": "Not controlling this robot"})
            return
        if robot.operational_mode not in ("MANUAL", "MAPPING"):
            self.send_json({"type": "error", "message": "Robot is not in manual or mapping mode"})
            return
        if robot.system_status != "ONLINE":
            self.send_json({"type": "error", "message": "Robot is offline"})
            return
        MQTTPublisher.publish(
            f"warehouse/robots/{robot_id}/cmd_manual",
            command,
            qos=0,
        )

    def robot_pose(self, event):
        self.send_json({
            "type": "robot.pose",
            "robot_id": event["robot_id"],
            "x": event["x"],
            "y": event["y"],
            "yaw": event["yaw"],
        })

    def robot_status(self, event):
        self.send_json({
            "type": "robot.status",
            "robot_id": event["robot_id"],
            "system_status": event["system_status"],
        })

    def robot_mode(self, event):
        self.send_json({
            "type": "robot.mode",
            "robot_id": event["robot_id"],
            "operational_mode": event["operational_mode"],
            "controlled_by": event.get("controlled_by"),
        })

    def robot_mission(self, event):
        self.send_json({
            "type": "robot.mission",
            "robot_id": event["robot_id"],
            "status": event["status"],
        })

    def order_update(self, event):
        self.send_json({
            "type": "order.update",
            "order": event["order"],
        })

    def map_preview(self, event):
        logger.info(f"map_preview called for robot {event['robot_id']}, image size: {len(event['image_base64'])}")
        self.send_json({
            "type": "map.preview",
            "robot_id": event["robot_id"],
            "image_base64": event["image_base64"],
        })
