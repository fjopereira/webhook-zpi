from django.contrib import admin
from .models import MessageLog


@admin.register(MessageLog)
class MessageLogAdmin(admin.ModelAdmin):
    list_display = [
        'created_at', 
        'phone', 
        'message_preview', 
        'is_group', 
        'broadcast', 
        'forwarding_status_badge',
        'forwarded_at',
        'message_id'
    ]
    
    list_filter = [
        ('is_group', admin.BooleanFieldListFilter),
        ('broadcast', admin.BooleanFieldListFilter),
        ('external_system_status', admin.ChoicesFieldListFilter),
        ('created_at', admin.DateFieldListFilter),
        ('forwarded_at', admin.DateFieldListFilter),
    ]
    
    search_fields = [
        'phone', 
        'message', 
        'message_id',
        'external_system_response'
    ]
    
    readonly_fields = [
        'created_at', 
        'message_id',
        'is_group',
        'phone',
        'message',
        'broadcast',
        'external_system_status',
        'external_system_response',
        'external_system_status_code',
        'forwarded_at'
    ]
    
    ordering = ['-created_at']
    
    # Campos para exibição detalhada
    fieldsets = (
        ('Informações da Mensagem', {
            'fields': ('created_at', 'message_id', 'phone', 'message', 'is_group', 'broadcast')
        }),
        ('Status do Reencaminhamento', {
            'fields': ('external_system_status', 'external_system_status_code', 'forwarded_at'),
            'classes': ('collapse',)
        }),
        ('Resposta do Sistema Externo', {
            'fields': ('external_system_response',),
            'classes': ('collapse',),
            'description': 'Resposta completa recebida do sistema externo durante o reencaminhamento.'
        }),
    )
    
    # Ações personalizadas
    actions = ['mark_as_pending', 'retry_forwarding']
    
    # Personalização da listagem
    list_per_page = 50  # Mais itens por página
    
    # Personalização dos filtros de data
    date_hierarchy = 'created_at'
    
    def message_preview(self, obj):
        return obj.message[:100] + '...' if len(obj.message) > 100 else obj.message
    message_preview.short_description = 'Mensagem'
    
    def forwarding_status_badge(self, obj):
        """Exibe o status do reencaminhamento com cores e ícones"""
        if obj.external_system_status == 'success':
            return '<span style="color: green; font-weight: bold;">✅ Sucesso</span>'
        elif obj.external_system_status == 'failed':
            return '<span style="color: red; font-weight: bold;">❌ Falha</span>'
        elif obj.external_system_status == 'pending':
            return '<span style="color: orange; font-weight: bold;">⏳ Pendente</span>'
        else:
            return '<span style="color: gray;">❓ N/A</span>'
    forwarding_status_badge.short_description = 'Status Reencaminhamento'
    forwarding_status_badge.allow_tags = True
    
    def mark_as_pending(self, request, queryset):
        """Marca mensagens selecionadas como pendentes para reencaminhamento"""
        updated = queryset.update(external_system_status='pending')
        self.message_user(request, f'{updated} mensagem(s) marcada(s) como pendente(s) para reencaminhamento.')
    mark_as_pending.short_description = "Marcar como pendente para reencaminhamento"
    
    def retry_forwarding(self, request, queryset):
        """Marca mensagens falhadas para nova tentativa de reencaminhamento"""
        failed_messages = queryset.filter(external_system_status='failed')
        updated = failed_messages.update(external_system_status='pending')
        self.message_user(request, f'{updated} mensagem(s) marcada(s) para nova tentativa de reencaminhamento.')
    retry_forwarding.short_description = "Tentar reencaminhar novamente (apenas falhas)"
    
    def has_add_permission(self, request):
        return False  # Não permitir adicionar manualmente
    
    def has_change_permission(self, request, obj=None):
        return False  # Não permitir editar
    
    def has_delete_permission(self, request, obj=None):
        return True  # Permitir deletar
    
    # Personalização da busca
    def get_search_results(self, request, queryset, search_term):
        """Busca personalizada incluindo status de reencaminhamento"""
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        
        if search_term:
            # Buscar também por status de reencaminhamento
            status_filters = queryset.filter(
                external_system_status__icontains=search_term
            )
            queryset = queryset | status_filters
            
        return queryset, use_distinct
