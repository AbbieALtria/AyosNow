from django.contrib import admin
from django.urls import include, path
from core.views import healthz, readyz

urlpatterns = [
    path("healthz", healthz),
    path("readyz", readyz),
    path("admin/", admin.site.urls),
    path("api/v1/", include("api.urls")),
    path("app/", include("customer_portal.urls")),
    path("provider/", include("provider_portal.urls")),
    path("ops/", include("ops_portal.urls")),
]
