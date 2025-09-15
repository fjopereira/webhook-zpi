from django.urls import path
from .views import zapi_on_message_received, healthz, dashboard, index, consulta_status_carga


urlpatterns = [
    path('', index, name='index'),
    path('dashboard/', dashboard, name='dashboard'),
    path('consulta-status-carga/', consulta_status_carga, name='consulta_status_carga'),
    path('webhooks/zapi/on-message-received/<str:url_token>/', zapi_on_message_received, name='zapi-on-message-received'),
    path('healthz', healthz, name='healthz'),
]

