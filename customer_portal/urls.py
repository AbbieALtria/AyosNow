from django.urls import path

from .views import app

urlpatterns = [
    path("", app, name="customer_portal"),
]
