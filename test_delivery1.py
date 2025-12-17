#!/usr/bin/env python
"""
Script de teste para o webhook de delivery com o novo formato Meta/WhatsApp.

Uso:
    python test_delivery1.py
"""

import requests
import json

# Configurações
WEBHOOK_URL = (
    "http://127.0.0.1:8000/webhooks/delivery-callback/token_delivery_secreto_123/"
)
INTERNAL_SYSTEM_URL = "http://127.0.0.1:8003"  # Ajuste conforme necessário

# Payload de teste no novo formato Meta/WhatsApp
test_payload = {
    "account": {"id": "xxxxxxxxxxx"},
    "bot": {"id": "xxxxxxxxxxxxxxx"},
    "statuses": [
        {
            "message": {
                "id": "689e10d582c55b6600178cdb",
                "message_key": "1",
                "status": "delivered",
                "timestamp": "1755189463",
                "platform_data": {
                    "id": "wamid.HBgMNTUzMTkzMDE4MjI1FQIAERgSMDQxMEFGQUIwRUFEMTAyNzMxAA==",
                    "status": "delivered",
                    "timestamp": "1755189463",
                    "recipient_id": "xxxxxxxx",
                    "conversation": {
                        "id": "f21f15432ef480e7736ce4ee0aaf1b2e",
                        "expiration_timestamp": "1755189463",
                        "origin": {"type": "utility"},
                    },
                    "pricing": {
                        "billable": False,
                        "pricing_model": "PMP",
                        "category": "utility",
                        "type": "free_customer_service",
                    },
                },
            }
        }
    ],
}

# Teste com múltiplos status (simulando sent → delivered → read)
test_payload_multiple = {
    "account": {"id": "xxxxxxxxxxx"},
    "bot": {"id": "xxxxxxxxxxxxxxx"},
    "statuses": [
        {
            "message": {
                "id": "689e10d582c55b6600178cdb",
                "message_key": "1",
                "status": "sent",
                "timestamp": "1755189460",
                "platform_data": {},
            }
        },
        {
            "message": {
                "id": "689e10d582c55b6600178cdb",
                "message_key": "1",
                "status": "delivered",
                "timestamp": "1755189463",
                "platform_data": {},
            }
        },
        {
            "message": {
                "id": "689e10d582c55b6600178cdb",
                "message_key": "1",
                "status": "read",
                "timestamp": "1755189465",
                "platform_data": {},
            }
        },
    ],
}


def test_single_status():
    """Testa webhook com status único."""
    print("\n" + "=" * 60)
    print("TESTE 1: Status único (delivered)")
    print("=" * 60)

    try:
        response = requests.post(
            WEBHOOK_URL, json=test_payload, headers={"Content-Type": "application/json"}
        )

        print(f"\nStatus Code: {response.status_code}")
        print("Response:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))

        if response.status_code == 200:
            print("\n✅ Teste passou!")
        else:
            print("\n❌ Teste falhou!")

    except Exception as e:
        print(f"\n❌ Erro ao fazer requisição: {e}")


def test_multiple_statuses():
    """Testa webhook com múltiplos status."""
    print("\n" + "=" * 60)
    print("TESTE 2: Múltiplos status (sent → delivered → read)")
    print("=" * 60)

    try:
        response = requests.post(
            WEBHOOK_URL,
            json=test_payload_multiple,
            headers={"Content-Type": "application/json"},
        )

        print(f"\nStatus Code: {response.status_code}")
        print("Response:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))

        if response.status_code == 200:
            data = response.json()
            print("\n✅ Teste passou!")
            print(f"   Processados: {data.get('processed', 0)}/{data.get('total', 0)}")
            print(f"   Falhados: {data.get('failed', 0)}")
        else:
            print("\n❌ Teste falhou!")

    except Exception as e:
        print(f"\n❌ Erro ao fazer requisição: {e}")


def test_invalid_payload():
    """Testa webhook com payload inválido."""
    print("\n" + "=" * 60)
    print("TESTE 3: Payload inválido (sem array statuses)")
    print("=" * 60)

    invalid_payload = {"account": {"id": "xxx"}, "bot": {"id": "yyy"}}

    try:
        response = requests.post(
            WEBHOOK_URL,
            json=invalid_payload,
            headers={"Content-Type": "application/json"},
        )

        print(f"\nStatus Code: {response.status_code}")
        print("Response:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))

        if response.status_code == 400:
            print("\n✅ Teste passou! (erro 400 esperado)")
        else:
            print("\n❌ Teste falhou! (esperava-se erro 400)")

    except Exception as e:
        print(f"\n❌ Erro ao fazer requisição: {e}")


if __name__ == "__main__":
    print("\n🧪 TESTES DO WEBHOOK DE DELIVERY")
    print(f"URL: {WEBHOOK_URL}")
    print(
        "\n⚠️  ATENÇÃO: Certifique-se de ter configurado o WEBHOOK_URL com o token correto!"
    )
    print("⚠️  ATENÇÃO: O servidor Django deve estar rodando em http://127.0.0.1:8000")

    input("\nPressione ENTER para continuar...")

    # Executar testes
    test_single_status()
    test_multiple_statuses()
    test_invalid_payload()

    print("\n" + "=" * 60)
    print("TESTES CONCLUÍDOS")
    print("=" * 60)
    print(
        "\n💡 Verifique os logs do Django e o dashboard para ver os registros criados."
    )
    print(f"   Dashboard: {INTERNAL_SYSTEM_URL}/dashboard/?tab=delivery")
