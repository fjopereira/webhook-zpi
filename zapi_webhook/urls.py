from django.urls import path
from .views import (
    zapi_on_message_received,
    healthz,
    dashboard,
    index,
    consulta_status_carga,
    api_consulta_carga,
)


urlpatterns = [
    path("", index, name="index"),
    path("dashboard/", dashboard, name="dashboard"),
    path("consulta-status-carga/", consulta_status_carga, name="consulta_status_carga"),
    path(
        "api/consulta-carga/<str:carga_number>/",
        api_consulta_carga,
        name="api_consulta_carga",
    ),
    path(
        "webhooks/zapi/on-message-received/<str:url_token>/",
        zapi_on_message_received,
        name="zapi-on-message-received",
    ),
    path("healthz", healthz, name="healthz"),
]
