# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Django-based webhook bridge that receives messages from Z-API (WhatsApp API) and forwards them to an internal system. The application includes a monitoring dashboard and a public load status query feature.

**Tech Stack:**
- Django 4.2.23
- PostgreSQL (production) / SQLite (development)
- Gunicorn server
- Python 3.11+
- Docker containerization

## Development Commands

### Environment Setup
```bash
# Windows - Activate virtual environment
venv\Scripts\activate

# Linux/Mac - Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Database Operations
```bash
# Run migrations
python manage.py migrate

# Create superuser (for dashboard access)
python manage.py createsuperuser

# Collect static files (production)
python manage.py collectstatic --noinput
```

### Development Server
```bash
# Run development server
python manage.py runserver
```

### Code Quality
```bash
# Run ruff linter/formatter
ruff check .
ruff format .
```

### Docker Operations
```bash
# Build image
docker build -t webhook-bridge .

# Run container
docker run -d --name webhook-bridge -p 8080:8080 webhook-bridge
```

## Architecture

### Application Structure

**Core Django Apps:**
- `core/` - Main Django project settings and URL configuration
- `zapi_webhook/` - Primary app handling webhook, dashboard, and load status queries
- `accounts/` - User authentication (login/logout views)

**Key Models:**
- `MessageLog` (zapi_webhook/models.py:4) - Stores all received messages with forwarding status tracking

### Request Flow

**Webhook Flow (Z-API → Internal System):**
1. Z-API sends POST to `/webhooks/zapi/on-message-received/<token>/`
2. Token validated against `ZAPI_WEBHOOK_URL_TOKEN` env var
3. Message saved to `MessageLog` database
4. Automatic cleanup of old messages (older than `MESSAGE_RETENTION_DAYS`)
5. Message forwarded to `EXTERNAL_SYSTEM_URL` via POST request
6. Forwarding result stored in database (`external_system_status`, `external_system_response`)

**Dashboard Flow:**
- Requires Django authentication (`@login_required`)
- Displays message logs with filtering (phone, status, date range, message_id, is_group, broadcast)
- Default filter: current day messages
- Pagination: 20 messages per page
- Statistics: total messages, unique contacts, groups, forwarding status, last message time

**Load Status Query Flow:**
- Public access (no authentication required)
- Accepts numeric load number only (sanitized via regex)
- Makes GET request to `CARGA_STATUS_URL/{load_number}`
- Extracts `msg` field from JSON response
- Comprehensive error handling and logging

**Delivery Webhook Flow (Callback from External System):**
- External system sends POST to `/webhooks/delivery-callback/<token>/`
- Token validated against `DELIVERY_WEBHOOK_TOKEN` env var
- Payload structure: `{"id": "message_id", "mensagem": "delivery status"}`
- Forwards to internal system route via POST: `/atualizaretornomensagemporid/{id}/`
- Internal route payload: `{"retorno_envio": "mensagem"}`
- All callbacks logged in `DeliveryWebhookLog` (including errors)
- Automatic cleanup of old logs (older than `DELIVERY_WEBHOOK_LOG_RETENTION_DAYS`)
- Dashboard displays delivery logs with filtering and statistics
- Supports multiple status types: success, not_found, forward_error, invalid_payload

### Environment Variables (Required)

**Django Configuration:**
- `DJANGO_SECRET_KEY` - Secret key for Django (required, no fallback)
- `DJANGO_DEBUG` - Debug mode (default: False)
- `DJANGO_ALLOWED_HOSTS` - Comma-separated allowed hosts
- `DJANGO_LOG_LEVEL` - Logging level (default: INFO)

**Database:**
- `DATABASE_URL` - PostgreSQL connection string (optional, defaults to SQLite)

**Webhook Configuration:**
- `ZAPI_WEBHOOK_URL_TOKEN` - Token for webhook authentication (required)
- `EXTERNAL_SYSTEM_URL` - URL to forward messages
- `EXTERNAL_SYSTEM_TIMEOUT` - Request timeout in seconds (default: 10)

**Message Retention:**
- `MESSAGE_RETENTION_DAYS` - Days to keep messages before auto-cleanup (default: 3)

**Load Status Query:**
- `CARGA_STATUS_URL` - External system URL for load status
- `CARGA_STATUS_TIMEOUT` - Request timeout in seconds (default: 10)

**Delivery Webhook:**
- `DELIVERY_WEBHOOK_TOKEN` - Token for delivery webhook authentication (required)
- `INTERNAL_SYSTEM_URL` - URL base of internal system to forward callbacks (default: http://127.0.0.1:8000)
- `INTERNAL_FORWARD_TIMEOUT` - Request timeout in seconds (default: 10)
- `DELIVERY_WEBHOOK_LOG_RETENTION_DAYS` - Days to keep delivery logs before auto-cleanup (default: 7)

### Security Features

**Production Security (when DEBUG=False):**
- HTTPS enforcement (`SECURE_SSL_REDIRECT=True`)
- Security headers (HSTS, XSS protection, content type sniffing)
- Secure cookies with HttpOnly and SameSite=Strict
- CSRF protection (disabled for webhook endpoint via `@csrf_exempt`)
- X-Frame-Options: DENY

**Input Validation:**
- Token validation for webhook access (zapi_webhook/views.py:69)
- Content-Type validation (application/json only)
- Carga number sanitization (digits only, max 20 chars) via `_sanitize_carga_number()` (zapi_webhook/views.py:244)

**Container Security:**
- Non-root user (appuser) in Docker
- Minimal base image (python:3.11-slim)

### Important Implementation Details

**Automatic Message Cleanup:**
- Triggered on every webhook POST request via `_cleanup_old_messages()` (zapi_webhook/views.py:22)
- Deletes messages older than `MESSAGE_RETENTION_DAYS`
- Logs deletion count

**Message Forwarding:**
- Only text messages are processed (ignores other message types)
- Forwarding status tracked: "pending" → "success" or "failed"
- Network errors caught and logged to database
- Response limited to 500 chars to prevent database bloat

**Dashboard Filtering:**
- Default behavior: shows only today's messages if no filters applied
- Filters persist via GET parameters
- All filters are optional and combinable

**Timezone:**
- Project timezone: America/Sao_Paulo (core/settings.py:157)
- Language: pt-br

**URL Patterns:**
- Webhook Z-API: `POST /webhooks/zapi/on-message-received/<token>/`
- Webhook Delivery: `POST /webhooks/delivery-callback/<token>/`
- Dashboard: `GET /dashboard/` (requires login, tabs: api, messages, delivery)
- Load status: `GET|POST /consulta-status-carga/` (public)
- API Consulta Carga: `GET /api/consulta-carga/<carga_number>/` (Bearer token required)
- Health check: `GET /healthz`
- Admin: `/admin/`
- Login/Logout: `/accounts/login/`, `/accounts/logout/`

**API de Consulta de Carga:**
- Endpoint RESTful para consulta de status de carga
- Autenticação via Bearer token no header `Authorization`
- Tokens gerenciados via Django Admin (modelo `ApiToken`)
- Rate limiting: 60 requisições/minuto por token
- Retorna JSON: `{"status": "0"|"1", "message": "..."}`
  - Status "0": Carga não encontrada (quando resposta contém "Verificar o número da carga informado")
  - Status "1": Carga encontrada com mensagem do sistema
- Logging completo em `ApiRequestLog` (IP, token, tempo, status)
- Dashboard possui aba dedicada para visualizar requisições da API
- CORS configurado via `CORS_ALLOWED_ORIGINS` (suporta IPs e domínios)

**Exemplo de requisição:**
```bash
curl -X GET "https://dominio.com/api/consulta-carga/12345/" \
  -H "Authorization: Bearer seu-token-aqui"
```

**Resposta sucesso (encontrado):**
```json
{
  "status": "1",
  "message": "Carga em trânsito"
}
```

**Resposta não encontrado:**
```json
{
  "status": "0",
  "message": ""
}
```

**Webhook de Retorno de Entrega:**
- Endpoint para receber callbacks do Meta/WhatsApp (via Z-API) sobre status de entrega
- Autenticação via token de URL (DELIVERY_WEBHOOK_TOKEN)
- Formato do payload (Meta/WhatsApp):
  ```json
  {
    "account": {"id": "xxxxxxxxxxx"},
    "bot": {"id": "xxxxxxxxxxxxxxx"},
    "statuses": [
      {
        "message": {
          "id": "689e10d582c55b6600178cdb",
          "message_key": "db539ae2-f44c-434f-a5ce-005d126f4774",
          "status": "sent|delivered|read|undelivered",
          "timestamp": "1755189463",
          "platform_data": {...}
        }
      }
    ]
  }
  ```
- Status possíveis: `sent`, `delivered`, `read`, `undelivered`
  - `sent` - Mensagem enviada
  - `delivered` - Mensagem entregue
  - `read` - Mensagem lida (apenas se usuário tiver confirmação de leitura ativa)
  - `undelivered` - Mensagem não entregue
- Sequência típica de status:
  - Com confirmação de leitura: `sent` → `delivered` → `read`
  - Sem confirmação de leitura: `sent` → `delivered`
  - Falha na entrega: `sent` → `undelivered`
- Processamento em lote: processa múltiplos status do array `statuses[]`
- Encaminhamento automático para sistema interno via POST (um por status)
- Logging completo em `DeliveryWebhookLog` (IP, payload, tempo, status)
- Dashboard possui aba dedicada para visualizar logs de delivery

**Exemplo de requisição (Meta/WhatsApp via Z-API):**
```bash
curl -X POST "https://dominio.com/webhooks/delivery-callback/seu-token-aqui/" \
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
          "platform_data": {
            "id": "wamid.HBgMNTUzMTkzMDE4MjI1FQIAERgSMDQxMEFGQUIwRUFEMTAyNzMxAA==",
            "status": "delivered",
            "timestamp": "1755189463",
            "recipient_id": "xxxxxxxx"
          }
        }
      }
    ]
  }'
```

**Resposta sucesso:**
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

**Respostas de erro:**
- `401` - Token inválido: `{"detail": "Invalid token"}`
- `400` - JSON inválido: `{"detail": "Invalid JSON"}`
- `400` - Array statuses faltando/inválido: `{"detail": "Missing or invalid 'statuses' array"}`

**Encaminhamento automático (por cada status):**
- URL: `{INTERNAL_SYSTEM_URL}/atualizaretornomensagemporid/`
- Método: POST
- Payload: `{"id_mensagem": "message_key", "retorno_envio": "status"}`
- Timeout configurável via `INTERNAL_FORWARD_TIMEOUT`
- Status possíveis no encaminhamento: success, not_found, forward_error

### Testing Considerations

- No test suite currently exists
- When adding tests, consider mocking external requests (Z-API, EXTERNAL_SYSTEM_URL, CARGA_STATUS_URL)
- Test webhook token validation and unauthorized access
- Test message cleanup logic with different retention periods
- Test input sanitization for load status queries

### Deployment Notes

**Production Checklist:**
1. Set all required environment variables (especially `DJANGO_SECRET_KEY`, `ZAPI_WEBHOOK_URL_TOKEN`, `DELIVERY_WEBHOOK_TOKEN`)
2. Set `DJANGO_DEBUG=False`
3. Configure `ALLOWED_HOSTS` with actual domain
4. Use PostgreSQL (`DATABASE_URL`)
5. Run migrations before deployment
6. Configure `INTERNAL_SYSTEM_URL` for delivery webhook forwarding
6. Collect static files
7. Configure HTTPS/SSL certificates
8. Add domain to `CSRF_TRUSTED_ORIGINS` if needed

**Docker Deployment:**
- Gunicorn configured with 4 workers, gevent worker class
- Health check endpoint at `/healthz` (30s interval)
- Exposes port 8080
- Max requests per worker: 1000 (with jitter)

**Cloud Platform Examples:**
- Google Cloud Run: `gcloud run deploy webhook-bridge --source . --platform managed`
- Heroku: Requires `heroku-postgresql` addon

### Common Patterns

**When modifying webhook logic:**
- Maintain token validation (zapi_webhook/views.py:69)
- Preserve automatic cleanup call
- Update `MessageLog` model if changing tracked fields
- Ensure external system forwarding is non-blocking

**When adding new views:**
- Use `@login_required` for internal/admin views
- Add to zapi_webhook/urls.py
- Sanitize all user input (see `_sanitize_carga_number()` pattern)
- Add comprehensive logging (use logger, not print)
- Handle request exceptions explicitly

**When modifying database models:**
- Create and run migrations
- Update admin.py if admin interface needs changes
- Consider impact on message retention cleanup logic
