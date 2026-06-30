from rest_framework import serializers
from .models import Robot, Product, ProductPosition, Order, WarehouseMap


class RobotSerializer(serializers.ModelSerializer):
    controlled_by = serializers.SerializerMethodField()
    current_task = serializers.SerializerMethodField()

    class Meta:
        model = Robot
        fields = [
            "robot_id", "name", "system_status", "operational_mode",
            "controlled_by", "current_task", "pos_x", "pos_y", "yaw",
            "last_seen", "updated_at",
        ]

    def get_controlled_by(self, obj):
        return obj.controlled_by.username if obj.controlled_by else None

    def get_current_task(self, obj):
        return obj.current_task_id


class ProductSerializer(serializers.ModelSerializer):
    positions_count = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ["sku", "name", "positions_count", "updated_at"]

    def get_positions_count(self, obj):
        return obj.positions.count()


class ProductPositionSerializer(serializers.ModelSerializer):
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    map_name = serializers.CharField(source="map.name", read_only=True)

    class Meta:
        model = ProductPosition
        fields = [
            "id", "product", "product_sku", "product_name",
            "map", "map_name", "pos_x", "pos_y",
        ]
        extra_kwargs = {
            "product": {"write_only": True},
            "map": {"write_only": True},
        }


class ProductPositionCreateSerializer(serializers.ModelSerializer):
    product_sku = serializers.CharField(write_only=True)
    map_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = ProductPosition
        fields = ["product_sku", "map_id", "pos_x", "pos_y"]

    def create(self, validated_data):
        from .models import Product, WarehouseMap
        product = Product.objects.get(sku=validated_data.pop("product_sku"))
        map_obj = WarehouseMap.objects.get(id=validated_data.pop("map_id"))
        return ProductPosition.objects.create(
            product=product, map=map_obj, **validated_data
        )


class OrderSerializer(serializers.ModelSerializer):
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    assigned_robot = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id", "product", "product_sku", "product_name",
            "assigned_robot", "status", "created_at",
            "updated_at", "completed_at",
        ]
        extra_kwargs = {
            "product": {"write_only": True},
        }

    def get_assigned_robot(self, obj):
        return obj.assigned_robot_id


class OrderCreateSerializer(serializers.ModelSerializer):
    product_sku = serializers.CharField(write_only=True)

    class Meta:
        model = Order
        fields = ["product_sku"]


class WarehouseMapSerializer(serializers.ModelSerializer):
    scanned_by = serializers.SerializerMethodField()

    class Meta:
        model = WarehouseMap
        fields = [
            "id", "name", "scanned_by", "map_image", "resolution",
            "origin_x", "origin_y", "width_meters", "height_meters",
            "home_x", "home_y", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = [
            "map_image", "resolution", "origin_x", "origin_y",
            "width_meters", "height_meters", "is_active",
        ]

    def get_scanned_by(self, obj):
        return obj.scanned_by_id


class DashboardStatsSerializer(serializers.Serializer):
    active_robots = serializers.IntegerField()
    error_robots = serializers.IntegerField()
    pending_orders = serializers.IntegerField()
    completed_today = serializers.IntegerField()
