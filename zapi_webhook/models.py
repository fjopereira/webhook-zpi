from django.db import models


class MessageLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    is_group = models.BooleanField(default=False)
    message_id = models.CharField(max_length=255, db_index=True)
    phone = models.CharField(max_length=32, db_index=True)
    message = models.TextField(blank=True)
    broadcast = models.BooleanField(default=False)
    
    # Campos para rastrear o reencaminhamento
    external_system_status = models.CharField(max_length=50, blank=True, null=True, help_text="Status do reencaminhamento (success, failed, pending)")
    external_system_response = models.TextField(blank=True, null=True, help_text="Resposta do sistema externo")
    external_system_status_code = models.IntegerField(blank=True, null=True, help_text="Código de status HTTP da resposta")
    forwarded_at = models.DateTimeField(blank=True, null=True, help_text="Data/hora do reencaminhamento")

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.created_at} | {self.phone} | {self.message[:40]}"

