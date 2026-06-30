import json
import logging
from datetime import datetime, date
from django.db import transaction
from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token

from .models import Robot, Product, ProductPosition, Order, WarehouseMap
from .serializers import (
    RobotSerializer, ProductSerializer, ProductPositionSerializer,
    ProductPositionCreateSerializer, OrderSerializer, OrderCreateSerializer,
    WarehouseMapSerializer, DashboardStatsSerializer,
)
from .utils.mqtt_publisher import MQTTPublisher
from .utils.ws_notify import notify_robot_mode, notify_order_update, notify_robot_mission
from .utils.auto_assign import auto_assign_pending

logger = logging.getLogger("api")


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    username = request.data.get("username")
    password = request.data.get("password")
    user = authenticate(username=username, password=password)
    if user:
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user_id": user.id, "username": user.username})
    return Response({"error": "Invalid credentials"}, status=400)


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    return Response({"status": "ok", "timestamp": datetime.utcnow().isoformat()})


class RobotViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Robot.objects.all().order_by("robot_id")
    serializer_class = RobotSerializer
    lookup_field = "robot_id"

    @action(detail=True, methods=["put"])
    def set_mode(self, request, robot_id=None):
        mode = request.data.get("mode")
        if mode not in ("MANUAL", "IDLE"):
            return Response({"error": "Invalid mode"}, status=400)
        with transaction.atomic():
            robot = Robot.objects.select_for_update().get(robot_id=robot_id)
            if mode == "MANUAL":
                if robot.system_status != "ONLINE":
                    return Response({"error": "Robot is offline"}, status=409)
                if robot.operational_mode not in ("IDLE",):
                    return Response({"error": "Robot is not available"}, status=409)
                if robot.controlled_by is not None and robot.controlled_by != request.user:
                    return Response({"error": "Robot controlled by another user"}, status=409)
                robot.operational_mode = "MANUAL"
                robot.controlled_by = request.user
            elif mode == "IDLE":
                if robot.controlled_by is not None and robot.controlled_by != request.user:
                    return Response({"error": "Not your robot"}, status=403)
                if robot.operational_mode == "SEMI_MANUAL":
                    MQTTPublisher.publish(
                        f"warehouse/robots/{robot_id}/cmd_auto",
                        {"order_id": None, "action": "CANCEL"},
                    )
                MQTTPublisher.publish(
                    f"warehouse/robots/{robot_id}/cmd_manual",
                    "STOP",
                    qos=0,
                )
                robot.operational_mode = "IDLE"
                robot.controlled_by = None
            robot.save()
        notify_robot_mode(robot_id, robot.operational_mode,
                          robot.controlled_by.username if robot.controlled_by else None)
        auto_assign_pending(robot)
        return Response(RobotSerializer(robot).data)

    @action(detail=True, methods=["post"])
    def navigate(self, request, robot_id=None):
        x = request.data.get("x")
        y = request.data.get("y")
        if x is None or y is None:
            return Response({"error": "x and y are required"}, status=400)
        with transaction.atomic():
            robot = Robot.objects.select_for_update().get(robot_id=robot_id)
            if robot.system_status != "ONLINE":
                return Response({"error": "Robot is offline"}, status=409)
            if robot.controlled_by != request.user:
                return Response({"error": "Not your robot"}, status=403)
            if robot.operational_mode not in ("MANUAL", "SEMI_MANUAL"):
                return Response({"error": "Robot is not in manual mode"}, status=409)
            robot.operational_mode = "SEMI_MANUAL"
            robot.save()
        MQTTPublisher.publish(
            f"warehouse/robots/{robot_id}/cmd_auto",
            {
                "order_id": None,
                "action": "NAVIGATE",
                "waypoints": [{"x": float(x), "y": float(y)}],
            },
        )
        notify_robot_mode(robot_id, "SEMI_MANUAL", request.user.username)
        return Response(RobotSerializer(robot).data)

class WarehouseMapViewSet(viewsets.ModelViewSet):
    queryset = WarehouseMap.objects.all().order_by("-created_at")
    serializer_class = WarehouseMapSerializer

    def destroy(self, request, *args, **kwargs):
        map_obj = self.get_object()
        if map_obj.is_active:
            return Response({"error": "Cannot delete the active map"}, status=409)
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    def active(self, request):
        map_obj = WarehouseMap.objects.filter(is_active=True).first()
        if not map_obj:
            return Response({"error": "No active map set"}, status=404)
        return Response(WarehouseMapSerializer(map_obj).data)

    @action(detail=True, methods=["post"])
    def set_active(self, request, pk=None):
        confirm = request.data.get("confirm", False)
        target_map = self.get_object()
        if target_map.is_active:
            return Response({"error": "Map is already active"}, status=400)
        with transaction.atomic():
            active_robots = Robot.objects.filter(
                operational_mode__in=("AUTO", "MAPPING")
            ).select_for_update()
            if active_robots.exists():
                return Response({
                    "blocked": True,
                    "block_reason": "Cannot change active map while robots are active.",
                }, status=409)
            in_progress = Order.objects.filter(status="IN_PROGRESS").select_for_update()
            if in_progress.exists():
                return Response({
                    "blocked": True,
                    "block_reason": "Cannot change active map while orders are in progress.",
                }, status=409)
            pending_cancel = Order.objects.filter(
                status="PENDING"
            ).exclude(
                product__positions__map=target_map
            )
            cancel_count = pending_cancel.count()
            if not confirm:
                return Response({"pending_cancel_count": cancel_count, "blocked": False})
            for order in pending_cancel.select_for_update():
                order.status = "CANCELLED"
                order.save()
                notify_order_update(OrderSerializer(order).data)
            WarehouseMap.objects.filter(is_active=True).update(is_active=False)
            target_map.is_active = True
            target_map.save()
        return Response({"success": True, "cancelled_count": cancel_count})

    @action(detail=False, methods=["post"])
    def start_scan(self, request):
        robot_id = request.data.get("robot_id")
        mode = request.data.get("mode")
        map_name = request.data.get("map_name")
        if not all([robot_id, mode, map_name]):
            return Response({"error": "robot_id, mode, and map_name are required"}, status=400)
        with transaction.atomic():
            robot = Robot.objects.select_for_update().get(robot_id=robot_id)
            if robot.system_status != "ONLINE":
                return Response({"error": "Robot is offline"}, status=409)
            if robot.operational_mode != "IDLE":
                return Response({"error": "Robot is not idle"}, status=409)
            action = "START_MANUAL" if mode and mode.lower() == "manual" else "START_AUTO"
            robot.operational_mode = "MAPPING"
            robot.controlled_by = request.user
            robot.save()
        MQTTPublisher.publish(
            f"warehouse/robots/{robot_id}/cmd_mapping",
            {"action": action},
        )
        notify_robot_mode(robot_id, "MAPPING", request.user.username)
        return Response({"status": "scanning started"})

    @action(detail=False, methods=["post"])
    def stop_scan(self, request):
        robot_id = request.data.get("robot_id")
        map_name = request.data.get("map_name", "Scanned Map")
        if not robot_id:
            return Response({"error": "robot_id is required"}, status=400)
        with transaction.atomic():
            robot = Robot.objects.select_for_update().get(robot_id=robot_id)
            if robot.operational_mode != "MAPPING":
                return Response({"error": "Robot is not scanning"}, status=409)
            if robot.controlled_by != request.user:
                return Response({"error": "Not your robot"}, status=403)
        MQTTPublisher.publish(
            f"warehouse/robots/{robot_id}/cmd_mapping",
            {"action": "STOP_AND_SAVE", "map_name": map_name},
        )
        return Response({"status": "save requested"})

    @action(detail=False, methods=["post"])
    def cancel_scan(self, request):
        robot_id = request.data.get("robot_id")
        if not robot_id:
            return Response({"error": "robot_id is required"}, status=400)
        with transaction.atomic():
            robot = Robot.objects.select_for_update().get(robot_id=robot_id)
            if robot.operational_mode != "MAPPING":
                return Response({"error": "Robot is not scanning"}, status=409)
            if robot.controlled_by != request.user:
                return Response({"error": "Not your robot"}, status=403)
        MQTTPublisher.publish(
            f"warehouse/robots/{robot_id}/cmd_mapping",
            {"action": "CANCEL"},
        )
        with transaction.atomic():
            robot = Robot.objects.select_for_update().get(robot_id=robot_id)
            robot.operational_mode = "IDLE"
            robot.controlled_by = None
            robot.save()
        notify_robot_mode(robot_id, "IDLE", None)
        return Response({"status": "scan cancelled"})


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by("sku")
    serializer_class = ProductSerializer
    lookup_field = "sku"

    def perform_destroy(self, instance):
        if instance.orders.exists():
            return Response({"error": "Cannot delete product with order history"}, status=409)
        instance.delete()


class ProductPositionViewSet(viewsets.ModelViewSet):
    queryset = ProductPosition.objects.all().order_by("id")
    serializer_class = ProductPositionSerializer

    def get_serializer_class(self):
        if self.action == "create":
            return ProductPositionCreateSerializer
        return ProductPositionSerializer

    def get_queryset(self):
        queryset = ProductPosition.objects.all().order_by("id")
        map_id = self.request.query_params.get("map")
        if map_id:
            queryset = queryset.filter(map_id=map_id)
        return queryset


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all().order_by("-created_at")
    serializer_class = OrderSerializer

    def get_serializer_class(self):
        if self.action == "create":
            return OrderCreateSerializer
        return OrderSerializer

    def get_queryset(self):
        queryset = Order.objects.all().order_by("-created_at")
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        ordering = self.request.query_params.get("ordering")
        if ordering:
            queryset = queryset.order_by(ordering)
        return queryset

    def perform_create(self, serializer):
        product_sku = serializer.validated_data["product_sku"]
        try:
            product = Product.objects.get(sku=product_sku)
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=404)
        active_map = WarehouseMap.objects.filter(is_active=True).first()
        if not active_map:
            return Response({"error": "No active map set"}, status=400)
        has_pos = ProductPosition.objects.filter(product=product, map=active_map).exists()
        if not has_pos:
            return Response({"error": "Product has no position on the active map"}, status=400)
        order = Order.objects.create(product=product, status="PENDING")
        self._auto_assign(Order.objects.get(id=order.id))
        notify_order_update(OrderSerializer(Order.objects.get(id=order.id)).data)

    def _auto_assign(self, order):
        active_map = WarehouseMap.objects.filter(is_active=True).first()
        if not active_map:
            return
        try:
            pos = ProductPosition.objects.get(product=order.product, map=active_map)
        except ProductPosition.DoesNotExist:
            return
        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=order.id)
            available = Robot.objects.filter(
                system_status="ONLINE", operational_mode="IDLE"
            ).select_for_update()
            if not available.exists():
                return
            best_robot = None
            best_dist = float("inf")
            for robot in available:
                dx = robot.pos_x - pos.pos_x
                dy = robot.pos_y - pos.pos_y
                dist = dx * dx + dy * dy
                if dist < best_dist:
                    best_dist = dist
                    best_robot = robot
            if best_robot:
                order.assigned_robot = best_robot
                order.status = "IN_PROGRESS"
                order.save()
                best_robot.operational_mode = "AUTO"
                best_robot.current_task = order
                best_robot.save()
        if best_robot:
            MQTTPublisher.publish(
                f"warehouse/robots/{best_robot.robot_id}/cmd_auto",
                {
                    "order_id": order.id,
                    "action": "NAVIGATE",
                    "waypoints": [
                        {"x": pos.pos_x, "y": pos.pos_y},
                        {"x": active_map.home_x, "y": active_map.home_y},
                    ],
                },
            )
            notify_robot_mode(best_robot.robot_id, "AUTO", None)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=pk)
            if order.status not in ("PENDING", "IN_PROGRESS"):
                return Response({"error": "Order cannot be cancelled"}, status=409)
            if order.status == "IN_PROGRESS" and order.assigned_robot:
                robot = Robot.objects.select_for_update().get(robot_id=order.assigned_robot_id)
                MQTTPublisher.publish(
                    f"warehouse/robots/{robot.robot_id}/cmd_auto",
                    {"order_id": order.id, "action": "CANCEL"},
                )
                robot.operational_mode = "IDLE"
                robot.current_task = None
                robot.save()
                notify_robot_mode(robot.robot_id, "IDLE", None)
                order.status = "CANCELLED"
                order.save()
                notify_order_update(OrderSerializer(order).data)
                auto_assign_pending(robot)
                return Response(OrderSerializer(order).data)
            order.status = "CANCELLED"
            order.save()
        notify_order_update(OrderSerializer(order).data)
        return Response(OrderSerializer(order).data)


class DashboardViewSet(viewsets.ViewSet):
    @action(detail=False, methods=["get"])
    def stats(self, request):
        active_robots = Robot.objects.filter(system_status="ONLINE").count()
        error_robots = Robot.objects.filter(system_status="ERROR").count()
        pending_orders = Order.objects.filter(status="PENDING").count()
        completed_today = Order.objects.filter(
            status="COMPLETED", completed_at__date=date.today()
        ).count()
        data = DashboardStatsSerializer({
            "active_robots": active_robots,
            "error_robots": error_robots,
            "pending_orders": pending_orders,
            "completed_today": completed_today,
        }).data
        return Response(data)
