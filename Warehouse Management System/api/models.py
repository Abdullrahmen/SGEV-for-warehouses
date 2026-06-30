from django.db import models
from django.contrib.auth.models import User


class Robot(models.Model):
    SYSTEM_STATUS_CHOICES = [
        ("ONLINE", "Online"),
        ("OFFLINE", "Offline"),
        ("ERROR", "Error"),
    ]
    OPERATIONAL_MODE_CHOICES = [
        ("IDLE", "Idle"),
        ("AUTO", "Auto"),
        ("MANUAL", "Manual"),
        ("SEMI_MANUAL", "Semi-Manual"),
        ("MAPPING", "Mapping"),
    ]

    robot_id = models.CharField(max_length=50, primary_key=True)
    name = models.CharField(max_length=255)
    system_status = models.CharField(
        max_length=20, choices=SYSTEM_STATUS_CHOICES, default="OFFLINE"
    )
    operational_mode = models.CharField(
        max_length=20, choices=OPERATIONAL_MODE_CHOICES, default="IDLE"
    )
    controlled_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="controlled_robots"
    )
    current_task = models.ForeignKey(
        "Order", on_delete=models.SET_NULL, null=True, blank=True
    )
    pos_x = models.FloatField(default=0.0)
    pos_y = models.FloatField(default=0.0)
    yaw = models.FloatField(default=0.0)
    last_seen = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["system_status"]),
            models.Index(fields=["operational_mode"]),
        ]

    def __str__(self):
        return f"{self.robot_id} - {self.name}"


class Product(models.Model):
    sku = models.CharField(max_length=50, primary_key=True)
    name = models.CharField(max_length=255)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.sku} - {self.name}"


class WarehouseMap(models.Model):
    name = models.CharField(max_length=255)
    scanned_by = models.ForeignKey(
        Robot, on_delete=models.SET_NULL, null=True, blank=True
    )
    map_image = models.ImageField(upload_to="maps/")
    resolution = models.FloatField(help_text="meters per pixel")
    origin_x = models.FloatField(help_text="real-world X of bottom-left pixel")
    origin_y = models.FloatField(help_text="real-world Y of bottom-left pixel")
    width_meters = models.FloatField(editable=False)
    height_meters = models.FloatField(editable=False)
    home_x = models.FloatField(default=0.0)
    home_y = models.FloatField(default=0.0)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"


class ProductPosition(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="positions"
    )
    map = models.ForeignKey(
        WarehouseMap, on_delete=models.CASCADE, related_name="product_positions"
    )
    pos_x = models.FloatField()
    pos_y = models.FloatField()

    class Meta:
        unique_together = ("product", "map")

    def __str__(self):
        return f"{self.product.sku} on {self.map.name} at ({self.pos_x}, {self.pos_y})"


class Order(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("QUEUED_OFFLINE", "Queued Offline"),
        ("IN_PROGRESS", "In Progress"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
        ("CANCELLED", "Cancelled"),
    ]

    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    assigned_robot = models.ForeignKey(
        Robot, on_delete=models.SET_NULL, null=True, blank=True
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="PENDING"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"Order #{self.id} - {self.product.name} ({self.status})"
