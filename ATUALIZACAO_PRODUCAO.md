# Instruções para Atualização do Servidor de Produção

Este documento contém as instruções passo a passo para atualizar o servidor de produção com as novas funcionalidades implementadas.

---

## 🆕 ATUALIZAÇÃO 2025-12-17: Novo Formato Meta/WhatsApp para Delivery Webhook

### Resumo da Mudança

O webhook de delivery callback (`/webhooks/delivery-callback/<token>/`) foi atualizado para processar o novo formato de payload do Meta/WhatsApp via Z-API.

**O QUE MUDOU:**

**Formato ANTIGO** (não mais suportado):
```json
{
  "id": "message_id",
  "mensagem": "status da entrega"
}
```

**Formato NOVO** (atual):
```json
{
  "account": {"id": "..."},
  "bot": {"id": "..."},
  "statuses": [
    {
      "message": {
        "id": "...",
        "message_key": "db539ae2-f44c-434f-a5ce-005d126f4774",
        "status": "sent|delivered|read|undelivered",
        "timestamp": "1755189463",
        "platform_data": {...}
      }
    }
  ]
}
```

### Principais Alterações

1. **ID da mensagem:** Agora extraído de `statuses[].message.message_key` (não mais `id`)
2. **Status:** Agora extraído de `statuses[].message.status` (não mais `mensagem`)
3. **Processamento em lote:** Suporta múltiplos status no array `statuses[]`
4. **Status possíveis:** `sent`, `delivered`, `read`, `undelivered`
5. **Resposta atualizada:** Retorna resumo com total processado/falhado

### Ações Necessárias

**⚠️ IMPORTANTE:** Esta atualização é **COMPATÍVEL COM BREAKING CHANGE** - o formato antigo NÃO funcionará mais!

#### 1. Atualizar o Código

```bash
cd /caminho/para/webhook
git pull origin main
```

#### 2. Reiniciar o Servidor

Não há migrações de banco de dados nesta atualização. Apenas reinicie o servidor:

```bash
# Se usando systemd
sudo systemctl restart webhook.service

# Se usando Docker
docker-compose down && docker-compose up -d --build

# Se usando Docker standalone
docker restart webhook-bridge
```

#### 3. Atualizar Configuração no Z-API

Configure o Z-API para enviar callbacks de status de mensagem para:

```
URL: https://seu-dominio.com/webhooks/delivery-callback/SEU_TOKEN_DELIVERY/
Método: POST
Content-Type: application/json
```

O Z-API enviará automaticamente callbacks no novo formato quando:
- Mensagem for enviada (status: `sent`)
- Mensagem for entregue (status: `delivered`)
- Mensagem for lida pelo destinatário (status: `read`, se confirmação de leitura ativa)
- Mensagem não for entregue (status: `undelivered`)

#### 4. Testar o Webhook

Use o script de teste atualizado:

```bash
# Editar o script com seu token e URL
nano test_delivery1.py

# Executar os testes
python test_delivery1.py
```

Ou teste manualmente com curl:

```bash
curl -X POST "https://seu-dominio.com/webhooks/delivery-callback/SEU_TOKEN/" \
  -H "Content-Type: application/json" \
  -d '{
    "account": {"id": "xxxxxxxxxxx"},
    "bot": {"id": "xxxxxxxxxxxxxxx"},
    "statuses": [
      {
        "message": {
          "id": "689e10d582c55b6600178cdb",
          "message_key": "db539ae2-f44c-434f-a5ce-005d126f4774",
          "status": "delivered",
          "timestamp": "1755189463",
          "platform_data": {}
        }
      }
    ]
  }'
```

Resposta esperada:

```json
{
  "status": "ok",
  "processed": 1,
  "failed": 0,
  "total": 1,
  "results": [
    {
      "message_key": "db539ae2-f44c-434f-a5ce-005d126f4774",
      "status": "ok"
    }
  ]
}
```

#### 5. Validar no Dashboard

1. Acesse: `https://seu-dominio.com/dashboard/?tab=delivery`
2. Verifique se os callbacks estão sendo registrados corretamente
3. Confirme que o campo `delivery_message` mostra o status (sent/delivered/read/undelivered)

### Arquivos Modificados

- `zapi_webhook/views.py` - Função `delivery_webhook_callback()` completamente refatorada
- `CLAUDE.md` - Documentação atualizada com novo formato
- `test_delivery1.py` - Script de teste atualizado

### Rollback (se necessário)

Se precisar reverter para a versão anterior:

```bash
git checkout 379d287  # Commit anterior
sudo systemctl restart webhook.service
```

**Tempo estimado:** 5-10 minutos
**Downtime:** ~1-2 minutos (restart do servidor)
**Impacto:** BREAKING CHANGE - webhooks no formato antigo deixarão de funcionar

---

## 📋 Resumo das Alterações

Esta atualização adiciona as seguintes funcionalidades:

1. **Webhook de Retorno de Entrega (Delivery Callback)**
   - Endpoint para receber callbacks do sistema externo sobre status de entrega
   - Encaminhamento automático para sistema interno
   - Logs completos de todas as requisições
   - Nova aba no dashboard para monitoramento

2. **Melhorias Gerais**
   - Atualização de segurança no .gitignore
   - Documentação atualizada
   - Limpeza de arquivos desnecessários

---

## 🔧 Passo a Passo da Atualização

### 1. Backup do Servidor Atual

**IMPORTANTE:** Sempre faça backup antes de atualizar!

```bash
# Fazer backup do banco de dados (PostgreSQL)
pg_dump -U usuario -d webhook_db > backup_webhook_$(date +%Y%m%d_%H%M%S).sql

# Fazer backup dos arquivos de ambiente
cp .env .env.backup_$(date +%Y%m%d_%H%M%S)
```

### 2. Baixar as Atualizações do GitHub

```bash
# Navegar até o diretório do projeto
cd /caminho/para/webhook

# Verificar branch atual
git branch

# Fazer pull das atualizações
git pull origin main
```

### 3. Atualizar Variáveis de Ambiente

Edite o arquivo `.env` e adicione as seguintes variáveis novas:

```bash
# Webhook de retorno de entrega (delivery callback)
DELIVERY_WEBHOOK_TOKEN=gere-um-token-seguro-aqui
INTERNAL_SYSTEM_URL=http://127.0.0.1:8003
INTERNAL_FORWARD_TIMEOUT=10
DELIVERY_WEBHOOK_LOG_RETENTION_DAYS=7
```

**Como gerar um token seguro:**

```bash
# Opção 1: Python (recomendado)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Opção 2: OpenSSL
openssl rand -base64 32
```

**Exemplo de .env atualizado:**

```bash
# Configurações anteriores (manter como estão)
DJANGO_SECRET_KEY=sua-chave-existente
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=seu-dominio.com
DATABASE_URL=postgresql://user:pass@host:5432/webhook_db
ZAPI_WEBHOOK_URL_TOKEN=token-existente
EXTERNAL_SYSTEM_URL=https://seu-sistema.com/api
EXTERNAL_SYSTEM_TIMEOUT=10
MESSAGE_RETENTION_DAYS=3
CARGA_STATUS_URL=https://seu-sistema.com/consultastatuscarga/
CARGA_STATUS_TIMEOUT=10
API_REQUEST_LOG_RETENTION_DAYS=7
CORS_ALLOWED_ORIGINS=https://sistema-externo.com

# NOVAS VARIÁVEIS (adicionar estas)
DELIVERY_WEBHOOK_TOKEN=seu-token-delivery-gerado
INTERNAL_SYSTEM_URL=http://127.0.0.1:8003
INTERNAL_FORWARD_TIMEOUT=10
DELIVERY_WEBHOOK_LOG_RETENTION_DAYS=7
```

**⚠️ ATENÇÃO:**

- `DELIVERY_WEBHOOK_TOKEN`: Gere um token único e seguro
- `INTERNAL_SYSTEM_URL`: URL do sistema interno que receberá os callbacks (ajuste conforme seu ambiente)
- Não reutilize o token do ZAPI (`ZAPI_WEBHOOK_URL_TOKEN`)

### 4. Ativar Ambiente Virtual (se aplicável)

```bash
# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 5. Instalar/Atualizar Dependências

```bash
pip install -r requirements.txt
```

### 6. Aplicar Migrações do Banco de Dados

```bash
# Verificar migrações pendentes
python manage.py showmigrations

# Aplicar migrações
python manage.py migrate

# Você deve ver algo como:
# Running migrations:
#   Applying zapi_webhook.0004_deliverywebhooklog... OK
```

**O que essa migração faz:**

- Cria a tabela `DeliveryWebhookLog` para armazenar logs de callbacks de entrega
- Adiciona índices para melhor performance

### 7. Coletar Arquivos Estáticos

```bash
python manage.py collectstatic --noinput
```

### 8. Reiniciar o Servidor

**Se estiver usando Gunicorn com systemd:**

```bash
sudo systemctl restart webhook.service

# Verificar status
sudo systemctl status webhook.service
```

**Se estiver usando Docker:**

```bash
# Rebuild da imagem (se necessário)
docker build -t webhook-bridge .

# Parar o container atual
docker stop webhook-bridge
docker rm webhook-bridge

# Iniciar novo container com as variáveis atualizadas
docker run -d \
  --name webhook-bridge \
  -p 8080:8080 \
  --env-file .env \
  webhook-bridge

# Verificar logs
docker logs -f webhook-bridge
```

**Se estiver usando Docker Compose:**

```bash
# Rebuild e restart
docker-compose down
docker-compose up -d --build

# Verificar logs
docker-compose logs -f
```

### 9. Verificar se a Aplicação Está Funcionando

```bash
# Teste 1: Health check
curl https://seu-dominio.com/healthz

# Resposta esperada:
# {"status": "healthy"}

# Teste 2: Acessar o dashboard
# Abra no navegador: https://seu-dominio.com/dashboard/
# Verifique se a nova aba "Entregas (Delivery)" aparece
```

### 10. Configurar o Sistema Externo

Forneça ao sistema externo a URL e token do webhook de delivery:

**URL para configurar no sistema externo:**
```
https://seu-dominio.com/webhooks/delivery-callback/SEU_TOKEN_GERADO/
```

**Exemplo de requisição que o sistema externo deve fazer:**

```bash
curl -X POST "https://seu-dominio.com/webhooks/delivery-callback/SEU_TOKEN_GERADO/" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "3EB0123456789ABC",
    "mensagem": "Entregue com sucesso"
  }'
```

---

## 🧪 Testes de Validação

Após a atualização, realize os seguintes testes:

### Teste 1: Dashboard

1. Acesse: `https://seu-dominio.com/dashboard/`
2. Faça login com seu usuário Django
3. Verifique se há 3 abas: **Mensagens**, **API Consulta Carga**, **Entregas (Delivery)**
4. Clique na aba **Entregas (Delivery)**
5. Você deve ver a interface vazia (sem erros)

### Teste 2: Webhook de Delivery (Token Inválido)

```bash
curl -X POST "https://seu-dominio.com/webhooks/delivery-callback/token-errado/" \
  -H "Content-Type: application/json" \
  -d '{"id": "123", "mensagem": "teste"}'

# Resposta esperada: HTTP 401
# {"detail": "Invalid token"}
```

### Teste 3: Webhook de Delivery (Token Válido)

**IMPORTANTE:** Substitua `SEU_TOKEN_GERADO` pelo token configurado em `DELIVERY_WEBHOOK_TOKEN`

```bash
curl -X POST "https://seu-dominio.com/webhooks/delivery-callback/SEU_TOKEN_GERADO/" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "693ad320e067012b8ae9292f",
    "mensagem": "Teste de entrega bem-sucedido"
  }'

# Respostas possíveis:
# - HTTP 200: {"status": "ok", "message_id": "693ad320e067012b8ae9292f"}
# - HTTP 404: {"detail": "Message ID not found"} (se o ID não existir na base)
```

### Teste 4: Verificar Logs no Dashboard

1. Após executar o Teste 3, acesse o dashboard
2. Vá na aba **Entregas (Delivery)**
3. Você deve ver o registro do teste com:
   - Message ID: `693ad320e067012b8ae9292f`
   - Status: `not_found` ou `success` (dependendo se o ID existe)
   - IP da requisição
   - Timestamp

---

## 📊 Monitoramento

### Verificar Logs da Aplicação

```bash
# Se usando systemd
sudo journalctl -u webhook.service -f

# Se usando Docker
docker logs -f webhook-bridge

# Se usando Docker Compose
docker-compose logs -f
```

### Verificar Banco de Dados

```bash
# Conectar ao PostgreSQL
psql -U usuario -d webhook_db

# Verificar se a nova tabela foi criada
\dt zapi_webhook_deliverywebhooklog

# Ver registros de delivery (se houver)
SELECT id, message_id, webhook_status, created_at
FROM zapi_webhook_deliverywebhooklog
ORDER BY created_at DESC
LIMIT 10;

# Sair
\q
```

---

## 🚨 Troubleshooting

### Problema: Migração não aplica

**Erro:** `No migrations to apply`

**Solução:**

```bash
# Verificar se a migração existe
ls -la zapi_webhook/migrations/0004_deliverywebhooklog.py

# Se não existir, fazer pull novamente
git pull origin main

# Tentar novamente
python manage.py migrate
```

### Problema: Erro 500 ao acessar dashboard

**Possível causa:** Variáveis de ambiente faltando

**Solução:**

```bash
# Verificar se todas as variáveis estão definidas
python manage.py check

# Verificar logs
tail -f /var/log/webhook/error.log  # Ajuste o caminho conforme seu setup
```

### Problema: Webhook retorna 502

**Possível causa:** Sistema interno (`INTERNAL_SYSTEM_URL`) não está acessível

**Solução:**

1. Verifique se o `INTERNAL_SYSTEM_URL` está correto no `.env`
2. Teste a conectividade:

```bash
# Teste manual
curl -X POST "http://127.0.0.1:8003/atualizaretornomensagemporid/teste123/" \
  -H "Content-Type: application/json" \
  -d '{"retorno_envio": "teste"}'
```

3. Verifique os logs do sistema interno

### Problema: Logs não aparecem no dashboard

**Possível causa:** Permissões do banco de dados

**Solução:**

```bash
# Verificar se o modelo está registrado
python manage.py shell

>>> from zapi_webhook.models import DeliveryWebhookLog
>>> DeliveryWebhookLog.objects.count()
>>> exit()
```

---

## 📞 Suporte

Se encontrar problemas durante a atualização:

1. Verifique os logs da aplicação
2. Consulte a documentação no README.md
3. Revise o arquivo CLAUDE.md para detalhes técnicos
4. Abra uma issue no repositório GitHub

---

## ✅ Checklist Final

Após completar todos os passos, verifique:

- [ ] Backup do banco de dados realizado
- [ ] Código atualizado do GitHub (`git pull`)
- [ ] Variáveis de ambiente adicionadas ao `.env`
- [ ] Token de delivery gerado e configurado
- [ ] Migrações aplicadas com sucesso
- [ ] Servidor reiniciado
- [ ] Health check retorna status "healthy"
- [ ] Dashboard acessível e mostra 3 abas
- [ ] Webhook de delivery responde corretamente
- [ ] Sistema externo configurado com URL e token
- [ ] Testes de validação concluídos
- [ ] Logs da aplicação sem erros

---

## 📝 Informações Adicionais

**Commit da atualização:** `379d287`
**Data da atualização:** 2025-12-11
**Arquivos principais modificados:**
- `zapi_webhook/models.py` - Novo modelo DeliveryWebhookLog
- `zapi_webhook/views.py` - Novo endpoint delivery_webhook_callback
- `zapi_webhook/admin.py` - Novo admin para DeliveryWebhookLog
- `zapi_webhook/templates/dashboard.html` - Nova aba de entregas
- `core/settings.py` - Novas variáveis de ambiente

**Tempo estimado de atualização:** 15-30 minutos
**Downtime necessário:** ~2-5 minutos (apenas durante o restart do servidor)

---

**Boa atualização! 🚀**
