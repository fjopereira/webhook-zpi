# Project Overview

This is a Django project that serves as a secure webhook bridge between Z-API and an internal system. It's designed to receive messages from Z-API, log them into a database, and then forward them to a specified external system.

The project includes the following key features:

- A secure webhook endpoint that validates requests using a token.
- A monitoring dashboard to view and filter received messages.
- A public-facing page to check the status of a "carga" (shipment/load) from an external system.
- Automatic cleanup of old message logs.
- Detailed logging for all operations.

## Building and Running

### Prerequisites

- Python 3.11+
- Docker (for production)

### Development Setup

1.  **Clone the repository.**
2.  **Create and activate a virtual environment:**
    ```bash
    # Windows
    venv\Scripts\activate

    # Linux/Mac
    source venv/bin/activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Configure environment variables:**
    - Copy `.env.exemplo` to `.env`.
    - Fill in the required variables in the `.env` file, such as `DJANGO_SECRET_KEY`, `ZAPI_WEBHOOK_URL_TOKEN`, and `EXTERNAL_SYSTEM_URL`.
5.  **Run database migrations:**
    ```bash
    python manage.py migrate
    ```
6.  **Create a superuser (for dashboard access):**
    ```bash
    python manage.py createsuperuser
    ```
7.  **Start the development server:**
    ```bash
    python manage.py runserver
    ```

### Production (Docker)

1.  **Build the Docker image:**
    ```bash
    docker build -t webhook-bridge .
    ```
2.  **Run the container with the necessary environment variables:**
    ```bash
    docker run -d \
      --name webhook-bridge \
      -p 8080:8080 \
      -e DJANGO_SECRET_KEY="your-secure-key" \
      -e DJANGO_DEBUG="False" \
      -e DJANGO_ALLOWED_HOSTS="your-domain.com" \
      -e DATABASE_URL="postgresql://user:pass@host:5432/db" \
      -e ZAPI_WEBHOOK_URL_TOKEN="your-secure-token" \
      -e EXTERNAL_SYSTEM_URL="https://internal-system.com/api" \
      webhook-bridge
    ```

## Development Conventions

- **Configuration:** The project uses a `.env` file for managing environment variables, loaded by `python-dotenv` in `core/settings.py`.
- **Database:** It uses SQLite for local development and PostgreSQL for production. The configuration is handled by `dj-database-url`.
- **Linting:** The project uses `ruff` for linting, as indicated in `requirements.txt`.
- **Views:** The core logic is in `zapi_webhook/views.py`. The main webhook logic is in the `zapi_on_message_received` function.
- **Security:** The `README.md` and `core/settings.py` show a strong focus on security, with settings for HTTPS, secure headers, and token validation.
- **Templates:** HTML templates are located in the `templates/` and `accounts/templates/` directories.

### Nova API de Consulta de Carga

**Endpoint:** `GET /api/consulta-carga/<carga_number>/`

**Autenticação:** Bearer token (gerenciado via Django Admin)

**Rate Limiting:** 60 requisições/minuto por token

**Request:**
```
GET /api/consulta-carga/12345/
Authorization: Bearer seu-token-aqui
```

**Response Success:**
```json
{
  "status": "1",
  "message": "Carga em trânsito"
}
```

**Response Not Found:**
```json
{
  "status": "0",
  "message": ""
}
```

**Gerenciamento de Tokens:**
- Criar tokens via Django Admin em "Tokens de API"
- Token gerado automaticamente ao criar
- Pode ativar/desativar tokens
- Rastreamento de último uso

**Logging:**
- Todas requisições logadas em `ApiRequestLog`
- Visível no dashboard (aba "Requisições API")
- Métricas: IP, token usado, tempo de processamento, status

**CORS:**
- Configurar domínios permitidos via `CORS_ALLOWED_ORIGINS` no .env
