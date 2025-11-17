from django.db import models
import secrets
from django.contrib.auth.models import User


class MessageLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    is_group = models.BooleanField(default=False)
    message_id = models.CharField(max_length=255, db_index=True)
    phone = models.CharField(max_length=32, db_index=True)
    message = models.TextField(blank=True)
    broadcast = models.BooleanField(default=False)

    # Campos para rastrear o reencaminhamento
    external_system_status = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Status do reencaminhamento (success, failed, pending)",
    )
    external_system_response = models.TextField(
        blank=True, null=True, help_text="Resposta do sistema externo"
    )
    external_system_status_code = models.IntegerField(
        blank=True, null=True, help_text="Código de status HTTP da resposta"
    )
    forwarded_at = models.DateTimeField(
        blank=True, null=True, help_text="Data/hora do reencaminhamento"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.created_at} | {self.phone} | {self.message[:40]}"


class ApiToken(models.Model):
    """
    Token de autenticação para API de consulta de carga.
    Gerenciado via Django Admin.
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Nome identificador do token (ex: Sistema XYZ)",
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        editable=False,
        help_text="Token gerado automaticamente",
    )
    is_active = models.BooleanField(default=True, help_text="Token ativo ou revogado")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Usuário que criou o token",
    )
    last_used = models.DateTimeField(
        null=True, blank=True, help_text="Última vez que o token foi usado"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Token de API"
        verbose_name_plural = "Tokens de API"

    def save(self, *args, **kwargs):
        if not self.token:
            # Gerar token seguro de 64 caracteres
            self.token = secrets.token_urlsafe(48)
        super().save(*args, **kwargs)

    def __str__(self):
        status = "Ativo" if self.is_active else "Revogado"
        return f"{self.name} - {status}"


class ApiRequestLog(models.Model):
    """
    Log de requisições da API de consulta de carga.
    """

    REQUEST_STATUS_CHOICES = [
        ("success", "Sucesso"),
        ("invalid_token", "Token Inválido"),
        ("invalid_input", "Entrada Inválida"),
        ("system_error", "Erro do Sistema"),
        ("timeout", "Timeout"),
        ("connection_error", "Erro de Conexão"),
        ("rate_limited", "Rate Limit Excedido"),
    ]

    # Informações da requisição
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(
        help_text="IP do cliente que fez a requisição"
    )
    api_token = models.ForeignKey(
        ApiToken,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Token usado na requisição",
    )
    carga_number = models.CharField(
        max_length=20, db_index=True, help_text="Número da carga consultada"
    )

    # Status da requisição
    request_status = models.CharField(
        max_length=50,
        choices=REQUEST_STATUS_CHOICES,
        db_index=True,
        help_text="Status da requisição",
    )

    # Resposta enviada ao cliente
    response_status = models.CharField(
        max_length=1,
        choices=[("0", "Não encontrado"), ("1", "Encontrado")],
        blank=True,
        help_text="Status retornado ao cliente (0 ou 1)",
    )
    response_message = models.TextField(
        blank=True, help_text="Mensagem retornada ao cliente"
    )

    # Resposta do sistema interno
    internal_system_status_code = models.IntegerField(
        null=True, blank=True, help_text="Código HTTP do sistema interno"
    )
    internal_system_response = models.TextField(
        blank=True, help_text="Resposta bruta do sistema interno"
    )

    # Tempo de processamento
    processing_time_ms = models.IntegerField(
        null=True, blank=True, help_text="Tempo de processamento em milissegundos"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Log de Requisição API"
        verbose_name_plural = "Logs de Requisições API"

    def __str__(self):
        return f"{self.created_at} | {self.ip_address} | Carga: {self.carga_number} | {self.request_status}"
