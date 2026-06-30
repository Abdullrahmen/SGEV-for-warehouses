from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"robots", views.RobotViewSet)
router.register(r"maps", views.WarehouseMapViewSet)
router.register(r"products", views.ProductViewSet)
router.register(r"product-positions", views.ProductPositionViewSet)
router.register(r"orders", views.OrderViewSet)
router.register(r"dashboard", views.DashboardViewSet, basename="dashboard")

urlpatterns = [
    path("auth/login/", views.login_view, name="login"),
    path("health/", views.health_check, name="health"),
    path("", include(router.urls)),
]
