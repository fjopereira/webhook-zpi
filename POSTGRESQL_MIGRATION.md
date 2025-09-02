# Migração para PostgreSQL

Este documento descreve como migrar o projeto de SQLite para PostgreSQL.

## Alterações Realizadas

### 1. Dependências Adicionadas
- `psycopg2-binary==2.9.9` - Driver PostgreSQL para Python/Django
- `dj-database-url==2.1.0` - Parser de URLs de banco de dados

### 2. Configuração do Banco de Dados
O arquivo `core/settings.py` foi atualizado para suportar PostgreSQL via variável de ambiente `DATABASE_URL`, mantendo SQLite como fallback para desenvolvimento local.

### 3. Variáveis de Ambiente
O arquivo `config.env.example` foi atualizado com exemplos de configuração PostgreSQL.

## Como Usar

### Desenvolvimento Local com PostgreSQL

1. **Instalar PostgreSQL**
   ```bash
   # Windows (usando Chocolatey)
   choco install postgresql
   
   # Ou baixar do site oficial: https://www.postgresql.org/download/
   ```

2. **Criar banco de dados**
   ```sql
   CREATE DATABASE webhook_db;
   CREATE USER webhook_user WITH PASSWORD 'sua_senha_segura';
   GRANT ALL PRIVILEGES ON DATABASE webhook_db TO webhook_user;
   ```

3. **Configurar variável de ambiente**
   Criar arquivo `.env` baseado no `config.env.example`:
   ```env
   DATABASE_URL=postgresql://webhook_user:sua_senha_segura@localhost:5432/webhook_db
   ```

4. **Instalar dependências**
   ```bash
   pip install -r requirements.txt
   ```

5. **Executar migrações**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

### Desenvolvimento Local com SQLite (padrão)
Se não definir `DATABASE_URL`, o projeto continuará usando SQLite automaticamente.

### Produção
Configure a variável `DATABASE_URL` no seu ambiente de produção com a string de conexão do seu provedor PostgreSQL.

## Migração de Dados Existentes

Se você já tem dados no SQLite e quer migrar para PostgreSQL:

1. **Fazer backup dos dados**
   ```bash
   python manage.py dumpdata > backup.json
   ```

2. **Configurar PostgreSQL** (seguir passos acima)

3. **Executar migrações no PostgreSQL**
   ```bash
   python manage.py migrate
   ```

4. **Importar dados**
   ```bash
   python manage.py loaddata backup.json
   ```

## Vantagens do PostgreSQL

- **Performance**: Melhor para aplicações com muitos usuários
- **Recursos avançados**: JSON fields, full-text search, etc.
- **Escalabilidade**: Suporte a conexões concorrentes
- **Produção**: Padrão da indústria para aplicações Django em produção
- **Backup e recovery**: Ferramentas robustas de backup

## Troubleshooting

### Erro de conexão PostgreSQL
- Verificar se o PostgreSQL está rodando
- Confirmar credenciais na `DATABASE_URL`
- Verificar se o banco de dados existe

### Erro psycopg2
```bash
# Windows
pip install psycopg2-binary

# Linux/Mac se houver problemas
sudo apt-get install libpq-dev  # Ubuntu/Debian
brew install postgresql  # macOS
```
