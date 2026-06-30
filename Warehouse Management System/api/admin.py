from django.contrib import admin
from .models import Robot, Product, ProductPosition, Order, WarehouseMap

admin.site.register(Robot)
admin.site.register(Product)
admin.site.register(ProductPosition)
admin.site.register(Order)
admin.site.register(WarehouseMap)
