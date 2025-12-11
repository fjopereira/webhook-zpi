# Guia de Atualização em Produção

Este documento descreve os passos necessários para atualizar a aplicação no servidor de produção.

## Pré-requisitos

- Acesso SSH ao servidor de produção.
- Permissões para navegar até o diretório da aplicação.
- Permissões para reiniciar o serviço da aplicação (Docker/Gunicorn).

## Passos para Atualização

1.  **Acessar o Servidor:**
    Conecte-se ao servidor de produção via SSH.

2.  **Navegar para o Diretório da Aplicação:**
    ```bash
    cd /caminho/para/seu/projeto/webhook
    ```

3.  **Baixar as Atualizações:**
    Faça o pull das últimas alterações do repositório Git.
    ```bash
    git pull origin main
    ```
    *(Substitua `main` pelo nome da sua branch principal, se for diferente, como `master`)*

4.  **Instalar/Atualizar Dependências:**
    É importante verificar se há novas dependências ou atualizações. Recomenda-se usar o mesmo ambiente virtual da aplicação.
    ```bash
    # Ative o ambiente virtual (exemplo)
    # source /caminho/para/seu/venv/bin/activate

    pip install -r requirements.txt
    ```

5.  **Executar Migrações do Banco de Dados:**
    Aplique quaisquer novas migrações de banco de dados que tenham sido adicionadas.
    ```bash
    python manage.py migrate
    ```

6.  **Coletar Arquivos Estáticos:**
    Reuna todos os arquivos estáticos em um único diretório.
    ```bash
    python manage.py collectstatic --noinput
    ```

7.  **Reiniciar a Aplicação:**
    A forma de reiniciar dependerá de como a aplicação está sendo servida (Docker, Gunicorn, etc.).

    **Exemplo com Docker:**
    Se a aplicação estiver rodando em um contêiner Docker, você pode reconstruir a imagem e reiniciar o contêiner.
    ```bash
    # Pare o contêiner atual
    docker stop webhook-bridge

    # Remova o contêiner antigo
    docker rm webhook-bridge

    # Reconstrua a imagem com as novas atualizações
    docker build -t webhook-bridge .

    # Inicie o novo contêiner (use os mesmos parâmetros -e e -p da sua implantação original)
    docker run -d --name webhook-bridge -p 8080:8080 -e VAR1=VALOR1 webhook-bridge
    ```

    **Exemplo com Gunicorn (gerenciado por systemd):**
    Se o Gunicorn for gerenciado pelo `systemd`, reinicie o serviço.
    ```bash
    sudo systemctl restart gunicorn_webhook
    ```
    *(O nome do serviço `gunicorn_webhook` é um exemplo e pode variar)*

## Verificação Pós-Atualização

- Acesse a URL da aplicação para garantir que ela está online.
- Verifique os logs da aplicação para qualquer erro de inicialização.
  ```bash
  # Exemplo com Docker
  docker logs -f webhook-bridge

  # Exemplo com systemd/journalctl
  journalctl -u gunicorn_webhook -f
  ```
- Teste as principais funcionalidades, como o endpoint da API de consulta de carga, para confirmar que tudo está funcionando como esperado.
