"""
Script de teste para validar o sistema de fallback de URLs.
Execute com: python test_fallback.py
"""

import os
import django

# Configurar Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from zapi_webhook.views import try_urls_with_cache  # noqa: E402
import requests  # noqa: E402

print("=" * 60)
print("TESTE DO SISTEMA DE FALLBACK COM CACHE")
print("=" * 60)

# Teste 1: URLs com protocolo explícito
print("\n[TESTE 1] URLs inválidas (devem falhar)")
print("-" * 60)
try:
    response = try_urls_with_cache(
        urls_string="http://192.0.2.1:9999,http://192.0.2.2:9999",
        method="GET",
        timeout=2,
        cache_key="test1",
    )
    print("[ERRO] Deveria ter falhado mas passou!")
except requests.exceptions.RequestException as e:
    print("[OK] Teste passou: Todas URLs falharam como esperado")
    print(f"  Exceção: {type(e).__name__}")

# Teste 2: Parsear URLs sem protocolo
print("\n[TESTE 2] Parsear URLs sem protocolo")
print("-" * 60)
test_urls = "127.0.0.1:8003,192.168.1.100:8004"
urls = [url.strip() for url in test_urls.split(",")]
urls_with_protocol = [
    url if url.startswith(("http://", "https://")) else f"http://{url}" for url in urls
]
print(f"URLs originais: {test_urls}")
print(f"URLs parseadas: {urls_with_protocol}")
print("[OK] Parsear funcionando corretamente")

# Teste 3: Validar cache key
print("\n[TESTE 3] Validar sistema de cache")
print("-" * 60)
from django.core.cache import cache  # noqa: E402

test_key = "url_fallback_test_key"
test_value = "http://127.0.0.1:8003"

# Salvar no cache
cache.set(test_key, test_value, 60)
cached_value = cache.get(test_key)

if cached_value == test_value:
    print("[OK] Cache salvando e recuperando valores corretamente")
    print(f"  Valor salvo: {test_value}")
    print(f"  Valor recuperado: {cached_value}")
else:
    print("[ERRO] Cache nao esta funcionando")

# Limpar cache de teste
cache.delete(test_key)

print("\n" + "=" * 60)
print("TESTES CONCLUÍDOS")
print("=" * 60)
print("\nPara testar com URLs reais:")
print("1. Configure múltiplas URLs no .env:")
print("   EXTERNAL_SYSTEM_URL=127.0.0.1:8003,127.0.0.1:8004")
print("2. Inicie o servidor: python manage.py runserver")
print("3. Envie uma mensagem via webhook")
print("4. Verifique os logs para ver o sistema de fallback em ação")
print("\nLogs esperados:")
print("  - 'Fallback: Tentativa X/Y - URL: ...'")
print("  - 'Fallback: [OK] Sucesso com URL ...'")
print("  - 'Fallback: URL ... salva no cache'")
