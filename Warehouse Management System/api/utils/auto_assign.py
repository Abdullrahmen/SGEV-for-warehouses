from django.db import transaction
from api.models import Order, Robot, ProductPosition, WarehouseMap
from api.utils.mqtt_publisher import MQTTPublisher


def auto_assign_pending(robot):
    if robot.operational_mode != "IDLE" or robot.system_status != "ONLINE":
        return
    pending = Order.objects.filter(status="PENDING").order_by("created_at").first()
    if not pending:
        return
    active_map = WarehouseMap.objects.filter(is_active=True).first()
    if not active_map:
        return
    has_pos = ProductPosition.objects.filter(
        product=pending.product, map=active_map
    ).exists()
    if not has_pos:
        return
    with transaction.atomic():
        order = Order.objects.select_for_update().get(id=pending.id)
        robot = Robot.objects.select_for_update().get(robot_id=robot.robot_id)
        if order.status != "PENDING" or robot.operational_mode != "IDLE" or robot.system_status != "ONLINE":
            return
        order.assigned_robot = robot
        order.status = "IN_PROGRESS"
        order.save()
        robot.operational_mode = "AUTO"
        robot.current_task = order
        robot.save()
    try:
        pos = ProductPosition.objects.get(product=order.product, map=active_map)
    except ProductPosition.DoesNotExist:
        return
    MQTTPublisher.publish(
        f"warehouse/robots/{robot.robot_id}/cmd_auto",
        {
            "order_id": order.id,
            "action": "NAVIGATE",
            "waypoints": [
                {"x": pos.pos_x, "y": pos.pos_y},
                {"x": active_map.home_x, "y": active_map.home_y},
            ],
        },
    )
