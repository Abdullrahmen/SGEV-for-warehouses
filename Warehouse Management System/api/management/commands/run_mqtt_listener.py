import json
import base64
import logging
import signal
import threading
import time
from datetime import timedelta
from django.db import transaction, close_old_connections
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.files.base import ContentFile
import paho.mqtt.client as mqtt
from decouple import config

from api.models import Robot, Order, WarehouseMap, ProductPosition
from api.serializers import OrderSerializer
from api.utils.ws_notify import (
    notify_robot_pose, notify_robot_status, notify_robot_mode,
    notify_robot_mission, notify_order_update, notify_map_preview,
)
from api.utils.mqtt_publisher import MQTTPublisher
from api.utils.auto_assign import auto_assign_pending

logger = logging.getLogger("api.mqtt_listener")

POSE_THROTTLE_SECONDS = 1
MANUAL_TIMEOUT_SECONDS = 60
QUEUED_OFFLINE_TIMEOUT_MINUTES = 10
LAST_SEEN_OFFLINE_SECONDS = 30
PERIODIC_INTERVAL_SECONDS = 30


class Command(BaseCommand):
    help = "Runs the MQTT listener that subscribes to robot topics and updates the database."

    def __init__(self):
        super().__init__()
        self.client = None
        self._running = True
        self._pose_last_db_write = {}
        self._cmd_manual_timestamps = {}

    def handle(self, *args, **options):
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

        self.client = mqtt.Client()
        self.client.username_pw_set(
            config("MQTT_USERNAME"), config("MQTT_PASSWORD"),
        )
        self.client.reconnect_delay_set(min_delay=1, max_delay=60)

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

        self.client.connect(
            config("MQTT_BROKER_HOST", default="localhost"),
            config("MQTT_BROKER_PORT", default=1883, cast=int),
        )

        periodic_thread = threading.Thread(target=self._periodic_checks, daemon=True)
        periodic_thread.start()

        self.client.loop_forever()

    def _shutdown(self, signum, frame):
        logger.info("Shutting down MQTT listener...")
        self._running = False
        if self.client:
            self.client.disconnect()

    def _on_connect(self, client, userdata, flags, rc):
        logger.info(f"MQTT connected with result code {rc}")
        client.subscribe("warehouse/robots/+/system_status", qos=1)
        client.subscribe("warehouse/robots/+/pose", qos=0)
        client.subscribe("warehouse/robots/+/mission_status", qos=1)
        client.subscribe("warehouse/robots/+/cmd_manual", qos=0)
        client.subscribe("warehouse/robots/+/map_preview", qos=0)
        client.subscribe("warehouse/robots/+/map_complete", qos=1)

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload
        parts = topic.split("/")
        if len(parts) < 4:
            return
        robot_id = parts[2]
        subtopic = parts[3]
        try:
            if subtopic == "system_status":
                self._handle_status(robot_id, payload.decode())
            elif subtopic == "pose":
                self._handle_pose(robot_id, json.loads(payload.decode()))
            elif subtopic == "mission_status":
                self._handle_mission(robot_id, payload.decode())
            elif subtopic == "cmd_manual":
                self._handle_cmd_manual(robot_id)
            elif subtopic == "map_preview":
                self._handle_map_preview(robot_id, payload)
            elif subtopic == "map_complete":
                self._handle_map_complete(robot_id, json.loads(payload.decode()))
        except Exception as e:
            logger.error(f"Error processing {topic}: {e}", exc_info=True)

    def _handle_status(self, robot_id, status):
        with transaction.atomic():
            try:
                robot = Robot.objects.select_for_update().get(robot_id=robot_id)
            except Robot.DoesNotExist:
                robot = Robot.objects.create(
                    robot_id=robot_id,
                    name=robot_id,
                    system_status=status,
                    operational_mode="IDLE",
                )
                logger.info(f"Auto-created robot {robot_id}")
            old_status = robot.system_status
            robot.system_status = status
            if status == "ONLINE" and robot.operational_mode == "MAPPING":
                robot.operational_mode = "IDLE"
            robot.save()
        notify_robot_status(robot_id, status)
        if status == "ONLINE" and old_status != "ONLINE":
            self._reassign_queued_offline(robot_id)
        elif status == "OFFLINE" and old_status != "OFFLINE":
            self._handle_robot_went_offline(robot_id)

    def _handle_pose(self, robot_id, data):
        x = data.get("x", 0.0)
        y = data.get("y", 0.0)
        yaw = data.get("yaw", 0.0)
        notify_robot_pose(robot_id, x, y, yaw)
        now = time.time()
        last_write = self._pose_last_db_write.get(robot_id, 0)
        if now - last_write >= POSE_THROTTLE_SECONDS:
            with transaction.atomic():
                Robot.objects.filter(robot_id=robot_id).update(
                    pos_x=x, pos_y=y, yaw=yaw, last_seen=timezone.now()
                )
            self._pose_last_db_write[robot_id] = now

    def _handle_mission(self, robot_id, status):
        with transaction.atomic():
            robot = Robot.objects.select_for_update().get(robot_id=robot_id)
            if robot.current_task:
                try:
                    order = Order.objects.select_for_update().get(id=robot.current_task.id)
                    if order.status != "IN_PROGRESS":
                        logger.warning(f"Duplicate mission_status for order {order.id}, ignoring")
                        return
                    if status == "COMPLETED":
                        order.status = "COMPLETED"
                        order.completed_at = timezone.now()
                    elif status == "FAILED":
                        order.status = "FAILED"
                    order.save()
                    robot.operational_mode = "IDLE"
                    robot.current_task = None
                    robot.save()
                    notify_robot_mission(robot_id, status)
                    notify_robot_mode(robot_id, "IDLE", None)
                    notify_order_update(OrderSerializer(order).data)
                    self._auto_assign_pending(robot)
                except Order.DoesNotExist:
                    pass
            elif robot.operational_mode == "SEMI_MANUAL":
                if status in ("COMPLETED", "FAILED"):
                    robot.operational_mode = "MANUAL"
                    robot.save()
                    notify_robot_mission(robot_id, status)
                    notify_robot_mode(
                        robot_id, "MANUAL",
                        robot.controlled_by.username if robot.controlled_by else None,
                    )
                    self._cmd_manual_timestamps[robot_id] = time.time()
            elif robot.operational_mode == "AUTO" and not robot.current_task:
                robot.operational_mode = "IDLE"
                robot.save()
                notify_robot_mission(robot_id, status)
                notify_robot_mode(robot_id, "IDLE", None)
                self._auto_assign_pending(robot)

    def _handle_cmd_manual(self, robot_id):
        self._cmd_manual_timestamps[robot_id] = time.time()

    def _handle_map_preview(self, robot_id, payload):
        image_b64 = payload.decode("utf-8")
        notify_map_preview(robot_id, image_b64)

    def _handle_map_complete(self, robot_id, data):
        map_name = data.get("map_name", f"Map from {robot_id}")
        image_data = base64.b64decode(data["map_image_base64"])
        resolution = data.get("resolution", 0.05)
        origin_x = data.get("origin_x", 0.0)
        origin_y = data.get("origin_y", 0.0)
        width_meters = data.get("width_meters", 0.0)
        height_meters = data.get("height_meters", 0.0)
        image_file = ContentFile(image_data, name=f"{robot_id}_{int(time.time())}.png")
        with transaction.atomic():
            robot = Robot.objects.select_for_update().get(robot_id=robot_id)
            WarehouseMap.objects.create(
                name=map_name,
                scanned_by=robot,
                map_image=image_file,
                resolution=resolution,
                origin_x=origin_x,
                origin_y=origin_y,
                width_meters=width_meters,
                height_meters=height_meters,
            )
            robot.operational_mode = "IDLE"
            robot.controlled_by = None
            robot.save()
        notify_robot_mode(robot_id, "IDLE", None)

    def _reassign_queued_offline(self, robot_id):
        with transaction.atomic():
            orders = Order.objects.filter(
                assigned_robot__robot_id=robot_id, status="QUEUED_OFFLINE"
            ).select_for_update()
            for order in orders:
                order.status = "IN_PROGRESS"
                order.save()
                notify_order_update(OrderSerializer(order).data)
            if orders.exists():
                robot = Robot.objects.select_for_update().get(robot_id=robot_id)
                robot.operational_mode = "AUTO"
                robot.current_task = orders.first()
                robot.save()
                notify_robot_mode(robot_id, "AUTO", None)
                active_map = WarehouseMap.objects.filter(is_active=True).first()
                if active_map:
                    try:
                        pos = ProductPosition.objects.get(
                            product=orders.first().product, map=active_map
                        )
                        MQTTPublisher.publish(
                            f"warehouse/robots/{robot_id}/cmd_auto",
                            {
                                "order_id": orders.first().id,
                                "action": "NAVIGATE",
                                "waypoints": [
                                    {"x": pos.pos_x, "y": pos.pos_y},
                                    {"x": active_map.home_x, "y": active_map.home_y},
                                ],
                            },
                        )
                    except ProductPosition.DoesNotExist:
                        pass

    def _handle_robot_went_offline(self, robot_id):
        with transaction.atomic():
            try:
                robot = Robot.objects.select_for_update().get(robot_id=robot_id)
            except Robot.DoesNotExist:
                return
            if robot.current_task:
                try:
                    order = Order.objects.select_for_update().get(id=robot.current_task.id)
                    if order.status == "IN_PROGRESS":
                        order.status = "QUEUED_OFFLINE"
                        order.save()
                        notify_order_update(OrderSerializer(order).data)
                except Order.DoesNotExist:
                    pass
            if robot.operational_mode in ("MANUAL", "SEMI_MANUAL"):
                robot.operational_mode = "IDLE"
                robot.controlled_by = None
                robot.save()
                notify_robot_mode(robot_id, "IDLE", None)

    def _auto_assign_pending(self, robot):
        auto_assign_pending(robot)

    def _periodic_checks(self):
        while self._running:
            time.sleep(PERIODIC_INTERVAL_SECONDS)
            try:
                close_old_connections()
                self._check_manual_timeout()
                self._check_queued_offline_reassignment()
                self._check_last_seen_offline()
            except Exception as e:
                logger.error(f"Periodic check error: {e}", exc_info=True)

    def _check_manual_timeout(self):
        now = time.time()
        with transaction.atomic():
            robots = Robot.objects.filter(operational_mode="MANUAL").select_for_update()
            for robot in robots:
                last_cmd = self._cmd_manual_timestamps.get(robot.robot_id, 0)
                if now - last_cmd > MANUAL_TIMEOUT_SECONDS:
                    logger.warning(f"Manual control timeout for {robot.robot_id}")
                    MQTTPublisher.publish(
                        f"warehouse/robots/{robot.robot_id}/cmd_manual",
                        "STOP",
                        qos=0,
                    )
                    robot.operational_mode = "IDLE"
                    robot.controlled_by = None
                    robot.save()
                    notify_robot_mode(robot.robot_id, "IDLE", None)
                    self._auto_assign_pending(robot)

    def _check_queued_offline_reassignment(self):
        cutoff = timezone.now() - timedelta(minutes=QUEUED_OFFLINE_TIMEOUT_MINUTES)
        with transaction.atomic():
            orders = Order.objects.filter(
                status="QUEUED_OFFLINE", updated_at__lt=cutoff
            ).select_for_update()
            for order in orders:
                logger.warning(f"Reassigning QUEUED_OFFLINE order {order.id}")
                order.assigned_robot = None
                order.status = "PENDING"
                order.save()
                notify_order_update(OrderSerializer(order).data)

    def _check_last_seen_offline(self):
        cutoff = timezone.now() - timedelta(seconds=LAST_SEEN_OFFLINE_SECONDS)
        with transaction.atomic():
            robots = Robot.objects.filter(
                system_status="ONLINE", last_seen__lt=cutoff
            ).select_for_update()
            for robot in robots:
                logger.warning(f"Last-seen timeout for {robot.robot_id}")
                robot.system_status = "OFFLINE"
                if robot.operational_mode in ("MANUAL", "SEMI_MANUAL"):
                    robot.operational_mode = "IDLE"
                    robot.controlled_by = None
                robot.save()
                notify_robot_status(robot.robot_id, "OFFLINE")
                if robot.operational_mode == "IDLE" and not robot.controlled_by:
                    notify_robot_mode(robot.robot_id, "IDLE", None)
