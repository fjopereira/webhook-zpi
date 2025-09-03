# Z-API Webhook Bridge

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Django](https://img.shields.io/badge/django-4.2.23-green.svg)
![PostgreSQL](https://img.shields.io/badge/postgresql-ready-blue.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

Ponte segura entre Z-API e sistemas internos com dashboard de monitoramento.

## 🚀 Funcionalidades

- **Webhook seguro** com autenticação por token
- **Ponte automática** para sistema interno
- **Dashboard de monitoramento** em tempo real
- **Logs detalhados** de todas as mensagens
- **Filtros avançados** e estatísticas
- **Limpeza automática** de registros antigos
- **PostgreSQL** para produção
- **Interface responsiva** para monitoramento

## 🛠️ Tecnologias

- **Backend**: Django 4.2.23
- **Banco**: PostgreSQL (produção) / SQLite (desenvolvimento)
- **Servidor**: Gunicorn + Gevent
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
- **Sanitização de dados** JSON
- **Logs de auditoria** detalhados
- **Container não-root** no Docker

### ⚠️ **Considerações para Internet**
- Webhook **exposto publicamente** (necessário para Z-API)
- **Rate limiting** removido (adicione se necessário)
- **Firewall** recomendado no servidor
- **Monitoramento** de tentativas de acesso

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
