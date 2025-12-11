# Z-API Webhook Bridge

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Django](https://img.shields.io/badge/django-4.2.23-green.svg)
![PostgreSQL](https://img.shields.io/badge/postgresql-ready-blue.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

Ponte segura entre Z-API e sistemas internos com dashboard de monitoramento.

## 🚀 Funcionalidades

- **Webhook seguro** com autenticação por token
- **Ponte automática** para sistema interno
- **Webhook de delivery** para callbacks de status de entrega
- **Dashboard de monitoramento** em tempo real
- **Consulta de status de carga** pública (sem login)
- **API RESTful** com autenticação Bearer token e rate limiting
- **Logs detalhados** de todas as mensagens e callbacks
- **Filtros avançados** e estatísticas
- **Limpeza automática** de registros antigos
- **PostgreSQL** para produção
- **Interface responsiva** para monitoramento

## 🛠️ Tecnologias

- **Backend**: Django 4.2.23
- **Banco**: PostgreSQL (produção) / SQLite (desenvolvimento)
- **Servidor**: Gunicorn
- **Container**: Docker com Python 3.11
- **Segurança**: HTTPS, headers seguros, validação de token

## 📋 Pré-requisitos

### Desenvolvimento
- Python 3.11+
- pip
- Ambiente virtual

### Produção
- Docker
- PostgreSQL
- HTTPS/SSL

## 🔧 Instalação

1. **Clone o repositório**
```bash
git clone <url-do-repositorio>
cd webhook
```

2. **Ative o ambiente virtual**
```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

3. **Instale as dependências**
```bash
pip install -r requirements.txt
```

4. **🔐 Configure as variáveis de ambiente (IMPORTANTE!)**
```bash
# Copie o exemplo e configure
cp config.env.example .env
# Edite o arquivo .env com suas chaves secretas
```

5. **Execute as migrações**
```bash
python manage.py migrate
```

6. **Crie um superusuário (opcional)**
```bash
python manage.py createsuperuser
```

7. **Inicie o servidor**
```bash
python manage.py runserver
```

## 🔐 Configuração para Produção

### ⚠️ **Variáveis de Ambiente Obrigatórias**

```bash
# Django
DJANGO_SECRET_KEY=chave-256-bits-super-segura
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=seu-dominio.com,www.seu-dominio.com

# Banco PostgreSQL
DATABASE_URL=postgresql://user:password@host:5432/webhook_db

# Webhook Z-API
ZAPI_WEBHOOK_URL_TOKEN=token-unico-muito-seguro

# Sistema interno
EXTERNAL_SYSTEM_URL=https://seu-sistema-interno.com/api/webhook
EXTERNAL_SYSTEM_TIMEOUT=10

# Limpeza automática (dias)
MESSAGE_RETENTION_DAYS=3

# Consulta de status de carga
CARGA_STATUS_URL=https://seu-sistema.com/consultastatuscarga/
CARGA_STATUS_TIMEOUT=10
```

### 🚨 **Segurança Implementada:**

- ✅ **HTTPS obrigatório** em produção
- ✅ **Headers de segurança** (HSTS, XSS, etc.)
- ✅ **Cookies seguros** e HttpOnly
- ✅ **Validação de token** no webhook
- ✅ **Sanitização** de dados JSON
- ✅ **Logs de auditoria** completos

## 🌐 Uso

### Webhook Z-API
- **Endpoint**: `POST https://seu-dominio.com/webhooks/zapi/on-message-received/<token>/`
- **Função**: Recebe mensagens do Z-API e encaminha para sistema interno
- **Autenticação**: Token na URL (configurado em `ZAPI_WEBHOOK_URL_TOKEN`)
- **Limpeza**: Remove automaticamente registros antigos a cada recebimento

### Dashboard de Monitoramento
- **URL**: `https://seu-dominio.com/dashboard/`
- **Login**: Usuário Django necessário
- **Função**: Monitorar mensagens e status de encaminhamento

### Consulta de Status de Carga
- **URL**: `https://seu-dominio.com/consulta-status-carga/`
- **Login**: Não necessário (acesso público)
- **Função**: Consultar status de carga em sistema externo
- **Segurança**: Sanitização de dados, validação de entrada, logs de auditoria

### Health Check
- **URL**: `https://seu-dominio.com/healthz/`
- **Função**: Verificar status da aplicação

### 🧹 Limpeza Automática
- **Configuração**: `MESSAGE_RETENTION_DAYS` (padrão: 3 dias)
- **Execução**: Automática no webhook Z-API
- **Logs**: Registra quantidade de mensagens removidas

## 📊 Estrutura do Projeto

```
webhook/
├── core/          # Configurações do Django
├── zapi_webhook/            # App principal
│   ├── models.py            # Modelo MessageLog
│   ├── views.py             # Views webhook e dashboard
│   ├── urls.py              # URLs do app
│   └── admin.py             # Configuração do admin
├── templates/               # Templates HTML
├── manage.py               # Script de gerenciamento
├── requirements.txt        # Dependências Python
├── .env                    # Variáveis de ambiente (NÃO commitar!)
├── config.env.example      # Exemplo de configuração
├── generate_secrets.py     # Gerador de chaves seguras
└── README.md               # Documentação
```

## 🔌 Configuração do Z-API

1. Configure o webhook no painel do Z-API
2. URL: `https://seu-dominio.com/webhooks/zapi/on-message-received/<token>/`
3. Método: POST
4. Content-Type: application/json

## 📱 Formato das Mensagens

O webhook espera mensagens no formato:
```json
{
  "text": {
    "message": "Conteúdo da mensagem",
    "broadcast": false
  },
  "isGroup": false,
  "messageId": "unique-message-id",
  "phone": "5511999999999"
}
```

## 🚀 Deploy para Produção

### 1. **Preparação**
```bash
# Instalar dependências
pip install -r requirements.txt

# Executar migrações
python manage.py migrate

# Coletar arquivos estáticos
python manage.py collectstatic --noinput
```

### 2. **Docker (Recomendado)**
```bash
# Build da imagem
docker build -t webhook-bridge .

# Run com variáveis de ambiente
docker run -d \
  --name webhook-bridge \
  -p 8080:8080 \
  -e DJANGO_SECRET_KEY="sua-chave-segura" \
  -e DJANGO_DEBUG="False" \
  -e DJANGO_ALLOWED_HOSTS="seu-dominio.com" \
  -e DATABASE_URL="postgresql://user:pass@host:5432/db" \
  -e ZAPI_WEBHOOK_URL_TOKEN="token-seguro" \
  -e EXTERNAL_SYSTEM_URL="https://sistema-interno.com/api" \
  webhook-bridge
```

### 3. **Cloud Deploy**
```bash
# Google Cloud Run
gcloud run deploy webhook-bridge \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated

# Heroku
heroku create webhook-bridge
heroku addons:create heroku-postgresql:mini
git push heroku main
```

## 🔒 Segurança para Ponte Z-API

### ✅ **Implementado**
- **Token de autenticação** no webhook
- **HTTPS enforcement** em produção
- **Headers de segurança** completos
- **Validação de Content-Type**
- **Sanitização de dados** JSON e entrada de usuário
- **Logs de auditoria** detalhados
- **Container não-root** no Docker
- **Validação de entrada** na consulta de carga (apenas números)
- **Timeout configurável** para requisições externas

### ⚠️ **Considerações para Internet**
- Webhook **exposto publicamente** (necessário para Z-API)
- **Rate limiting** removido (adicione se necessário)
- **Firewall** recomendado no servidor
- **Monitoramento** de tentativas de acesso

## 📥 Webhook de Retorno de Entrega (Delivery Callback)

Sistema de callbacks para receber atualizações de status de entrega do sistema externo.

### Configuração

**Variáveis de ambiente:**
```bash
DELIVERY_WEBHOOK_TOKEN=token-unico-delivery-seguro
INTERNAL_SYSTEM_URL=http://127.0.0.1:8000
INTERNAL_FORWARD_TIMEOUT=10
DELIVERY_WEBHOOK_LOG_RETENTION_DAYS=7
```

### Endpoint

- **URL**: `POST https://seu-dominio.com/webhooks/delivery-callback/<token>/`
- **Autenticação**: Token na URL (configurado em `DELIVERY_WEBHOOK_TOKEN`)
- **Content-Type**: `application/json`

### Formato da Requisição

O sistema externo deve enviar callbacks no seguinte formato:

```json
{
  "id": "message_id_aqui",
  "mensagem": "Status da entrega"
}
```

### Exemplo de Uso

```bash
curl -X POST "https://seu-dominio.com/webhooks/delivery-callback/seu-token/" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "3EB0123456789ABC",
    "mensagem": "Entregue com sucesso"
  }'
```

### Respostas

**Sucesso (200):**
```json
{
  "status": "ok",
  "message_id": "3EB0123456789ABC"
}
```

**Erros:**
- `401` - Token inválido
- `400` - JSON inválido ou campo faltando
- `404` - ID de mensagem não encontrado
- `502` - Erro ao encaminhar para sistema interno

### Encaminhamento Automático

Callbacks recebidos são automaticamente encaminhados para:
- **Rota**: `{INTERNAL_SYSTEM_URL}/atualizaretornomensagemporid/{id}/`
- **Método**: POST
- **Payload**: `{"retorno_envio": "mensagem recebida"}`

### Monitoramento

Acesse o Dashboard em **Entregas (Delivery)** para visualizar:
- Total de callbacks recebidos
- Taxa de sucesso/erro
- Tempo médio de processamento
- Logs detalhados com filtros (message_id, status, período)

### Limpeza Automática

Logs antigos são removidos automaticamente após o período configurado em `DELIVERY_WEBHOOK_LOG_RETENTION_DAYS`.

## API de Consulta de Carga

### Autenticação

1. Acesse o Django Admin (`/admin/`)
2. Vá em "Tokens de API"
3. Crie um novo token com um nome identificador
4. Copie o token gerado (será exibido apenas uma vez)

### Uso

```bash
curl -X GET "https://seu-dominio.com/api/consulta-carga/12345/" \
  -H "Authorization: Bearer seu-token-aqui"
```

### Resposta

**Carga encontrada:**
```json
{
  "status": "1",
  "message": "Carga em trânsito - Previsão: 2 dias"
}
```

**Carga não encontrada:**
```json
{
  "status": "0",
  "message": ""
}
```

### Rate Limiting

- Limite: 60 requisições por minuto por token
- Resposta ao exceder: HTTP 429

### CORS

Configure domínios permitidos no `.env`:
```
CORS_ALLOWED_ORIGINS=https://sistema1.com,https://sistema2.com
```

### Monitoramento

Acesse o Dashboard (`/dashboard/`) para visualizar:
- Total de requisições
- Taxa de sucesso/falha
- IPs únicos
- Tempo médio de resposta
- Logs detalhados por carga, token, período

## 📝 Logs

- Todas as mensagens são logadas no console
- Mensagens são salvas no banco de dados
- Logs de erro para falhas na validação

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature
3. Commit suas mudanças
4. Push para a branch
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT.

## 🆘 Suporte

Para suporte, abra uma issue no repositório ou entre em contato.

---
