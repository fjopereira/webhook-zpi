from django.contrib import admin
from .models import MessageLog, ApiToken, ApiRequestLog


# Configuração existente do MessageLog (manter)
@admin.register(MessageLog)
class MessageLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "phone",
        "message_preview",
        "is_group",
        "external_system_status",
    )
    list_filter = (
        "is_group",
        "broadcast",
        "external_system_status",
        "created_at",
    )
    search_fields = ("phone", "message", "message_id")
    readonly_fields = (
        "created_at",
        "message_id",
        "phone",
        "message",
        "is_group",
        "broadcast",
        "external_system_status",
        "external_system_response",
        "external_system_status_code",
        "forwarded_at",
    )
    ordering = ("-created_at",)

    def message_preview(self, obj):
        return obj.message[:50] + "..." if len(obj.message) > 50 else obj.message

    message_preview.short_description = "Mensagem"


# ADICIONAR CONFIGURAÇÃO PARA ApiToken
@admin.register(ApiToken)
class ApiTokenAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "token_preview",
        "is_active",
        "created_at",
        "created_by",
        "last_used",
    )
    list_filter = ("is_active", "created_at", "last_used")
    search_fields = ("name", "token")
    readonly_fields = ("token", "created_at", "last_used")

    fieldsets = (
        ("Informações Básicas", {"fields": ("name", "is_active")}),
        (
            "Token",
            {
                "fields": ("token",),
                "description": "Token gerado automaticamente. Copie e guarde em local seguro.",
            },
        ),
        (
            "Auditoria",
            {
                "fields": ("created_at", "created_by", "last_used"),
                "classes": ("collapse",),
            },
        ),
    )

    def token_preview(self, obj):
        return f"{obj.token[:20]}..." if obj.token else "-"

    token_preview.short_description = "Token (Preview)"

    def save_model(self, request, obj, form, change):
        if not change:  # Se está criando novo token
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# ADICIONAR CONFIGURAÇÃO PARA ApiRequestLog
@admin.register(ApiRequestLog)
class ApiRequestLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "ip_address",
        "api_token",
        "carga_number",
        "request_status",
        "response_status",
        "processing_time_ms",
    )
    list_filter = (
        "request_status",
        "response_status",
        "created_at",
        "api_token",
    )
    search_fields = ("ip_address", "carga_number")
    readonly_fields = (
        "created_at",
        "ip_address",
        "api_token",
        "carga_number",
        "request_status",
        "response_status",
        "response_message",
        "internal_system_status_code",
        "internal_system_response",
        "processing_time_ms",
    )
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        # Não permitir adicionar manualmente
        return False

    def has_change_permission(self, request, obj=None):
        # Não permitir editar
        return False
