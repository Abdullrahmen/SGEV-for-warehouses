import logging
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from api.models import Robot, Product

logger = logging.getLogger("api")


class Command(BaseCommand):
    help = "Creates demo data: admin user, robots, and sample products."

    def handle(self, *args, **options):
        user, created = User.objects.get_or_create(
            username="admin",
            defaults={"is_staff": True, "is_superuser": True},
        )
        if created:
            user.set_password("admin123")
            user.save()
            Token.objects.create(user=user)
            logger.info("Created admin user (password: admin123)")
        else:
            logger.info("Admin user already exists")

        for rid, rname in [("R1", "Warehouse Bot Alpha"), ("R2", "Warehouse Bot Beta")]:
            robot, created = Robot.objects.get_or_create(
                robot_id=rid,
                defaults={
                    "name": rname,
                    "system_status": "OFFLINE",
                    "operational_mode": "IDLE",
                },
            )
            if created:
                logger.info(f"Created robot {rid}")
            else:
                logger.info(f"Robot {rid} already exists")

        products = [
            ("SKU-001", "Electronics Shelf A"),
            ("SKU-002", "Electronics Shelf B"),
            ("SKU-003", "Packing Materials"),
            ("SKU-004", "Bottled Water Pallet"),
            ("SKU-005", "Canned Goods Pallet"),
            ("SKU-006", "Office Supplies Shelf"),
            ("SKU-007", "Cleaning Supplies"),
            ("SKU-008", "Spare Parts Bin"),
        ]
        for sku, name in products:
            product, created = Product.objects.get_or_create(
                sku=sku, defaults={"name": name}
            )
            if created:
                logger.info(f"Created product {sku}")

        logger.info("Seed data complete")
