import json
import logging
import re
from typing import Optional
from django_ratelimit.decorators import ratelimit
import time
from .models import ApiToken, ApiRequestLog, DeliveryWebhookLog

from django.conf import settings
from django.http import HttpRequest, JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import render
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from datetime import timedelta
from django.db import models

from .models import MessageLog
from django.core.paginator import Paginator
from django.core.cache import cache
import requests


logger = logging.getLogger(__name__)


def _cleanup_old_messages():
    """
    Remove mensagens antigas baseado no parâmetro MESSAGE_RETENTION_DAYS.
    Esta função é chamada automaticamente no dashboard para manter a base limpa.
    """
    try:
        retention_days = getattr(settings, "MESSAGE_RETENTION_DAYS", 5)
        cutoff_date = timezone.now() - timedelta(days=retention_days)

        # Contar quantos registros serão deletados
        old_messages_count = MessageLog.objects.filter(
            created_at__lt=cutoff_date
        ).count()

        if old_messages_count > 0:
            # Deletar mensagens antigas
            deleted_count, _ = MessageLog.objects.filter(
                created_at__lt=cutoff_date
            ).delete()
            logger.info(
                f"Limpeza automática: {deleted_count} mensagens antigas removidas (mais de {retention_days} dias)"
            )
            return deleted_count
        else:
            logger.debug(
                f"Limpeza automática: nenhuma mensagem antiga encontrada (retenção: {retention_days} dias)"
            )
            return 0

    except Exception as e:
        logger.error(f"Erro durante limpeza automática de mensagens: {e}")
        return 0


def _cleanup_old_api_requests():
    """
    Remove logs de requisição da API antigos.
    """
    try:
        retention_days = getattr(settings, "API_REQUEST_LOG_RETENTION_DAYS", 7)
        cutoff_date = timezone.now() - timedelta(days=retention_days)
        deleted_count, _ = ApiRequestLog.objects.filter(
            created_at__lt=cutoff_date
        ).delete()
        if deleted_count > 0:
            logger.info(
                f"Limpeza automática: {deleted_count} logs de API antigos removidos."
            )
    except Exception as e:
        logger.error(f"Erro durante limpeza automática de logs da API: {e}")


def _cleanup_old_delivery_logs():
    """
    Remove logs de delivery antigos baseado em DELIVERY_WEBHOOK_LOG_RETENTION_DAYS.
    Chamada automaticamente no webhook de delivery.
    Padrão idêntico ao _cleanup_old_messages().
    """
    try:
        retention_days = getattr(settings, "DELIVERY_WEBHOOK_LOG_RETENTION_DAYS", 7)
        cutoff_date = timezone.now() - timedelta(days=retention_days)
        deleted_count, _ = DeliveryWebhookLog.objects.filter(
            created_at__lt=cutoff_date
        ).delete()
        if deleted_count > 0:
            logger.info(
                f"Limpeza automática: {deleted_count} logs de delivery removidos "
                f"(mais de {retention_days} dias)"
            )
        return deleted_count
    except Exception as e:
        logger.error(f"Erro durante limpeza automática de logs de delivery: {e}")
        return 0


def try_urls_with_cache(
    urls_string: str,
    method: str = "GET",
    timeout: int = 10,
    cache_key: str = "default",
    cache_timeout: int = 300,
    **kwargs,
) -> requests.Response:
    """
    Tenta fazer requisição HTTP em múltiplas URLs com sistema de cache inteligente.

    O sistema tenta primeiro a URL que funcionou anteriormente (cache), depois tenta
    todas as URLs em ordem até encontrar uma que funcione.

    Args:
        urls_string: String com URLs separadas por vírgula (ex: "127.0.0.1:8003,192.168.1.100:8004")
        method: Método HTTP (GET, POST, etc)
        timeout: Timeout por tentativa em segundos
        cache_key: Chave única para identificar este grupo de URLs no cache
        cache_timeout: Tempo em segundos que a URL bem-sucedida fica em cache (padrão: 5min)
        **kwargs: Argumentos adicionais para requests (json, headers, etc)

    Returns:
        requests.Response: Resposta da requisição bem-sucedida

    Raises:
        requests.exceptions.RequestException: Se todas as URLs falharem
    """
    # Parsear URLs da string
    urls = [url.strip() for url in urls_string.split(",") if url.strip()]

    if not urls:
        raise ValueError("Nenhuma URL válida fornecida")

    # Adicionar http:// se não tiver protocolo
    urls = [
        url if url.startswith(("http://", "https://")) else f"http://{url}"
        for url in urls
    ]

    # Tentar obter URL do cache
    cache_full_key = f"url_fallback_{cache_key}"
    cached_url = cache.get(cache_full_key)

    # Lista de URLs para tentar (cache primeiro, depois as outras)
    urls_to_try = []
    if cached_url and cached_url in urls:
        urls_to_try.append(cached_url)
        # Adicionar as outras URLs (sem repetir a do cache)
        urls_to_try.extend([url for url in urls if url != cached_url])
        logger.debug(f"Fallback: Tentando primeiro URL do cache: {cached_url}")
    else:
        urls_to_try = urls
        logger.debug("Fallback: Cache vazio ou inválido, tentando URLs em ordem")

    last_exception = None
    failed_urls = []

    # Tentar cada URL
    for i, url in enumerate(urls_to_try, 1):
        try:
            logger.info(f"Fallback: Tentativa {i}/{len(urls_to_try)} - URL: {url}")
            start_time = time.time()

            # Fazer requisição
            response = requests.request(
                method=method, url=url, timeout=timeout, **kwargs
            )

            elapsed_ms = int((time.time() - start_time) * 1000)

            # Verificar se foi bem-sucedido (status 2xx ou 3xx)
            if 200 <= response.status_code < 400:
                logger.info(
                    f"Fallback: ✓ Sucesso com URL {url} - "
                    f"Status: {response.status_code} - Tempo: {elapsed_ms}ms"
                )

                # Salvar no cache
                if url != cached_url:
                    cache.set(cache_full_key, url, cache_timeout)
                    logger.info(
                        f"Fallback: URL {url} salva no cache por {cache_timeout}s"
                    )

                # Log de falhas anteriores (se houver)
                if failed_urls:
                    logger.warning(
                        f"Fallback: URLs que falharam antes do sucesso: {', '.join(failed_urls)}"
                    )

                return response
            else:
                # Status de erro HTTP
                failed_urls.append(url)
                logger.warning(
                    f"Fallback: ✗ URL {url} retornou status {response.status_code} - "
                    f"Tempo: {elapsed_ms}ms"
                )
                last_exception = requests.exceptions.HTTPError(
                    f"HTTP {response.status_code}", response=response
                )

        except requests.exceptions.Timeout:
            failed_urls.append(url)
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.warning(f"Fallback: ✗ Timeout na URL {url} após {elapsed_ms}ms")
            last_exception = requests.exceptions.Timeout(f"Timeout ao acessar {url}")

        except requests.exceptions.ConnectionError as e:
            failed_urls.append(url)
            logger.warning(f"Fallback: ✗ Erro de conexão na URL {url}: {str(e)[:100]}")
            last_exception = e

        except requests.exceptions.RequestException as e:
            failed_urls.append(url)
            logger.warning(f"Fallback: ✗ Erro na URL {url}: {str(e)[:100]}")
            last_exception = e

    # Se chegou aqui, todas as URLs falharam
    logger.error(
        f"Fallback: ✗✗✗ TODAS as {len(urls_to_try)} URLs falharam! "
        f"URLs tentadas: {', '.join(failed_urls)}"
    )

    # Limpar cache se todas falharam
    if cached_url:
        cache.delete(cache_full_key)
        logger.info("Fallback: Cache limpo devido a falhas consecutivas")

    # Levantar a última exceção
    if last_exception:
        raise last_exception
    else:
        raise requests.exceptions.RequestException(
            f"Todas as URLs falharam: {', '.join(failed_urls)}"
        )


def _url_token_is_valid(url_token: str) -> bool:
    expected = getattr(settings, "ZAPI_WEBHOOK_URL_TOKEN", "")
    return bool(expected) and url_token == expected


def _delivery_token_is_valid(url_token: str) -> bool:
    """
    Valida token do webhook de delivery.
    Padrão idêntico ao _url_token_is_valid() existente.
    """
    expected = getattr(settings, "DELIVERY_WEBHOOK_TOKEN", "")
    return bool(expected) and url_token == expected


@csrf_exempt
@require_http_methods(["POST"])
# @ratelimit(key='ip', rate='100/m', method='POST', block=True)  # Temporariamente desabilitado
def zapi_on_message_received(request: HttpRequest, url_token: str) -> HttpResponse:
    # Executar limpeza automática de mensagens antigas
    _cleanup_old_messages()

    # Verificar se o token é válido
    if not _url_token_is_valid(url_token):
        logger.warning("Invalid URL token for Z-API webhook")
        return JsonResponse({"detail": "Invalid token"}, status=401)

    content_type = request.headers.get("Content-Type", "")
    if "application/json" not in content_type:
        return JsonResponse({"detail": "Unsupported Media Type"}, status=415)

    try:
        body_bytes = request.body or b""
        payload = json.loads(body_bytes.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)

    # Log only text messages; ignore other message kinds
    text_block = payload.get("text") if isinstance(payload, dict) else None
    if isinstance(text_block, dict) and "message" in text_block:
        is_group = payload.get("isGroup", False)
        message_id = payload.get("messageId", "")
        phone = payload.get("phone", "")
        message = text_block.get("message", "")
        broadcast = text_block.get("broadcast", False)

        # Save to database
        try:
            message_log = MessageLog.objects.create(
                is_group=is_group,
                message_id=message_id,
                phone=phone,
                message=message,
                broadcast=broadcast,
                external_system_status="pending",
            )
            logger.info(f"Message saved to database: {message_id}")
        except Exception as e:
            logger.error(f"Error saving message to database: {e}")
            return JsonResponse({"detail": "Database error"}, status=500)

        # Forward data to another system
        try:
            forward_data = {
                "is_group": is_group,
                "message_id": message_id,
                "phone": phone,
                "message": message,
                "broadcast": broadcast,
            }

            # Usar sistema de fallback com múltiplas URLs
            response = try_urls_with_cache(
                urls_string=settings.EXTERNAL_SYSTEM_URL,
                method="POST",
                timeout=settings.EXTERNAL_SYSTEM_TIMEOUT,
                cache_key="external_system",
                cache_timeout=300,  # 5 minutos
                json=forward_data,
            )

            # Update database with forwarding results
            if response.status_code == 200:
                message_log.external_system_status = "success"
                message_log.external_system_response = response.text[
                    :500
                ]  # Limit response size
                message_log.external_system_status_code = response.status_code
                message_log.forwarded_at = timezone.now()
                logger.info(
                    f"Data forwarded successfully to external system: {message_id}"
                )
            else:
                message_log.external_system_status = "failed"
                message_log.external_system_response = (
                    f"HTTP {response.status_code}: {response.text[:500]}"
                )
                message_log.external_system_status_code = response.status_code
                message_log.forwarded_at = timezone.now()
                logger.warning(
                    f"Failed to forward data to external system. Status: {response.status_code}, Response: {response.text}"
                )

            # Save the updated record
            message_log.save()

        except requests.exceptions.RequestException as e:
            # Update database with error information
            message_log.external_system_status = "failed"
            message_log.external_system_response = f"Network error: {str(e)[:500]}"
            message_log.forwarded_at = timezone.now()
            message_log.save()
            logger.error(f"Error forwarding data to external system: {e}")

        # Simple console logging
        print(
            f"Z-API text received | isGroup={is_group} | messageId={message_id} | phone={phone} | message='{message}' | broadcast={broadcast}"
        )

    # Return success response
    return JsonResponse({"status": "ok"}, status=200)


@require_http_methods(["GET"])
def healthz(request: HttpRequest) -> HttpResponse:
    return JsonResponse({"status": "ok"}, status=200)


@csrf_exempt
@require_http_methods(["POST"])
def delivery_webhook_callback(request: HttpRequest, url_token: str) -> HttpResponse:
    """
    Webhook para receber callbacks de entrega do Meta/WhatsApp via Z-API.

    Formato esperado:
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

    Encaminha para rota interna via POST com {"id_mensagem": "message_key", "retorno_envio": "status"}
    """
    start_time = time.time()

    # Executar limpeza automática
    _cleanup_old_delivery_logs()

    # 1. Validar token
    if not _delivery_token_is_valid(url_token):
        logger.warning("Invalid URL token for delivery webhook")
        return JsonResponse({"detail": "Invalid token"}, status=401)

    # 2. Validar Content-Type
    content_type = request.META.get("CONTENT_TYPE", "")
    if "application/json" not in content_type:
        return JsonResponse({"detail": "Unsupported Media Type"}, status=415)

    # 3. Parsear JSON
    try:
        body_bytes = request.body or b""
        payload = json.loads(body_bytes.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        # Registrar log de payload inválido
        try:
            ip_address = request.META.get("REMOTE_ADDR", "unknown")
            DeliveryWebhookLog.objects.create(
                message_id="invalid",
                delivery_message="",
                raw_payload={},
                ip_address=ip_address,
                webhook_status="invalid_payload",
                internal_route_response="Invalid JSON",
                processing_time_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as e:
            logger.error(f"Erro ao registrar log de payload inválido: {e}")
        return JsonResponse({"detail": "Invalid JSON"}, status=400)

    # 4. Extrair array de statuses
    statuses = payload.get("statuses", [])

    if not isinstance(statuses, list) or len(statuses) == 0:
        # Registrar log de estrutura inválida
        try:
            ip_address = request.META.get("REMOTE_ADDR", "unknown")
            DeliveryWebhookLog.objects.create(
                message_id="missing",
                delivery_message="",
                raw_payload=payload,
                ip_address=ip_address,
                webhook_status="invalid_payload",
                internal_route_response="Missing or invalid 'statuses' array",
                processing_time_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as e:
            logger.error(f"Erro ao registrar log de estrutura inválida: {e}")
        return JsonResponse(
            {"detail": "Missing or invalid 'statuses' array"}, status=400
        )

    # 5. Processar cada status recebido
    ip_address = request.META.get("REMOTE_ADDR", "unknown")
    internal_system_url = getattr(
        settings, "INTERNAL_SYSTEM_URL", "http://127.0.0.1:8000"
    )
    timeout = getattr(settings, "INTERNAL_FORWARD_TIMEOUT", 10)

    processed_count = 0
    failed_count = 0
    results = []

    for status_item in statuses:
        # Extrair dados do status
        message_data = status_item.get("message", {})
        message_key = message_data.get("message_key", "")
        delivery_status = message_data.get("status", "")

        if not message_key:
            logger.warning("Status sem message_key encontrado no payload")
            failed_count += 1
            continue

        if not delivery_status:
            logger.warning(f"Status sem campo 'status' para message_key: {message_key}")
            failed_count += 1
            continue

        # Encaminhar para rota interna
        internal_url = f"{internal_system_url}/atualizaretornomensagemporid/"
        forward_payload = {"id_mensagem": message_key, "retorno_envio": delivery_status}

        try:
            response = requests.post(
                internal_url,
                json=forward_payload,
                timeout=timeout,
                headers={"Content-Type": "application/json"},
            )

            # Processar resposta
            if response.status_code == 404:
                # ID não encontrado
                DeliveryWebhookLog.objects.create(
                    message_id=message_key,
                    delivery_message=delivery_status,
                    raw_payload=payload,
                    ip_address=ip_address,
                    webhook_status="not_found",
                    internal_route_status_code=404,
                    internal_route_response=response.text[:500],
                    processing_time_ms=int((time.time() - start_time) * 1000),
                )
                logger.warning(
                    f"Message ID not found in internal system: {message_key}"
                )
                results.append({"message_key": message_key, "status": "not_found"})
                failed_count += 1

            elif 200 <= response.status_code < 400:
                # Sucesso
                DeliveryWebhookLog.objects.create(
                    message_id=message_key,
                    delivery_message=delivery_status,
                    raw_payload=payload,
                    ip_address=ip_address,
                    webhook_status="success",
                    internal_route_status_code=response.status_code,
                    internal_route_response=response.text[:500],
                    processing_time_ms=int((time.time() - start_time) * 1000),
                )
                logger.info(
                    f"Delivery callback processed successfully: {message_key} - Status: {delivery_status}"
                )
                results.append({"message_key": message_key, "status": "ok"})
                processed_count += 1

            else:
                # Erro HTTP
                DeliveryWebhookLog.objects.create(
                    message_id=message_key,
                    delivery_message=delivery_status,
                    raw_payload=payload,
                    ip_address=ip_address,
                    webhook_status="forward_error",
                    internal_route_status_code=response.status_code,
                    internal_route_response=response.text[:500],
                    processing_time_ms=int((time.time() - start_time) * 1000),
                )
                logger.error(
                    f"Internal route returned error {response.status_code} for message {message_key}"
                )
                results.append({"message_key": message_key, "status": "forward_error"})
                failed_count += 1

        except requests.exceptions.RequestException as e:
            # Erro de rede/timeout
            DeliveryWebhookLog.objects.create(
                message_id=message_key,
                delivery_message=delivery_status,
                raw_payload=payload,
                ip_address=ip_address,
                webhook_status="forward_error",
                internal_route_response=f"Network error: {str(e)[:500]}",
                processing_time_ms=int((time.time() - start_time) * 1000),
            )
            logger.error(f"Network error forwarding to internal system: {e}")
            results.append({"message_key": message_key, "status": "network_error"})
            failed_count += 1

        except Exception as e:
            # Erro inesperado
            logger.error(f"Unexpected error processing status for {message_key}: {e}")
            try:
                DeliveryWebhookLog.objects.create(
                    message_id=message_key,
                    delivery_message=delivery_status,
                    raw_payload=payload,
                    ip_address=ip_address,
                    webhook_status="forward_error",
                    internal_route_response=f"Unexpected error: {str(e)[:500]}",
                    processing_time_ms=int((time.time() - start_time) * 1000),
                )
            except Exception:
                pass
            results.append({"message_key": message_key, "status": "error"})
            failed_count += 1

    # 6. Retornar resposta final
    total_statuses = len(statuses)
    response_data = {
        "status": "ok",
        "processed": processed_count,
        "failed": failed_count,
        "total": total_statuses,
        "results": results,
    }

    logger.info(
        f"Delivery webhook completed: {processed_count}/{total_statuses} processed, "
        f"{failed_count} failed - Time: {int((time.time() - start_time) * 1000)}ms"
    )

    return JsonResponse(response_data, status=200)


@login_required
def dashboard(request):
    # Determinar qual aba está ativa
    active_tab = request.GET.get("tab", "api")  # "api" ou "messages"

    if active_tab == "messages":
        # Lógica existente para MessageLog
        phone = request.GET.get("phone", "")
        status = request.GET.get("status", "")
        is_group = request.GET.get("is_group", "")
        broadcast = request.GET.get("broadcast", "")
        start_date_str = request.GET.get("start_date")
        end_date_str = request.GET.get("end_date")
        message_id = request.GET.get("message_id", "")

        messages = MessageLog.objects.all()

        # Filtro padrão: apenas se nenhum outro filtro for fornecido
        if not any(
            [
                phone,
                status,
                is_group,
                broadcast,
                start_date_str,
                end_date_str,
                message_id,
            ]
        ):
            today = timezone.now().date()
            messages = messages.filter(created_at__date=today)
            start_date = today.strftime("%Y-%m-%d")
            end_date = today.strftime("%Y-%m-%d")
        else:
            start_date = start_date_str or ""
            end_date = end_date_str or ""

        if message_id:
            messages = messages.filter(message_id=message_id)
        if phone:
            messages = messages.filter(phone__icontains=phone)
        if status:
            messages = messages.filter(external_system_status=status)
        if start_date:
            messages = messages.filter(created_at__date__gte=start_date)
        if end_date:
            messages = messages.filter(created_at__date__lte=end_date)
        if is_group != "":
            messages = messages.filter(is_group=(is_group == "true"))
        if broadcast != "":
            messages = messages.filter(broadcast=(broadcast == "true"))

        # Estatísticas MessageLog (baseadas nos filtros)
        total_messages = messages.count()
        unique_contacts = messages.values("phone").distinct().count()
        groups = messages.filter(is_group=True).count()
        forwarded = messages.filter(external_system_status="forwarded").count()
        failed = messages.filter(external_system_status="failed").count()
        last_message = messages.order_by("-created_at").first()
        last_message_time = (
            last_message.created_at.strftime("%d/%m/%Y %H:%M:%S")
            if last_message
            else "-"
        )

        paginator = Paginator(messages.order_by("-created_at"), 20)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context = {
            "active_tab": "messages",
            "stats": {
                "total_messages": total_messages,
                "unique_contacts": unique_contacts,
                "groups": groups,
                "forwarded": forwarded,
                "failed": failed,
                "last_message": last_message_time,
            },
            "message_id": message_id,
            "messages": page_obj,
            "phone": phone,
            "status": status,
            "start_date": start_date,
            "end_date": end_date,
            "is_group": is_group,
            "broadcast": broadcast,
            "is_paginated": page_obj.has_other_pages(),
            "page_obj": page_obj,
        }
    elif active_tab == "delivery":
        # Lógica para DeliveryWebhookLog
        message_id = request.GET.get("message_id", "")
        webhook_status = request.GET.get("webhook_status", "")
        start_date_str = request.GET.get("start_date")
        end_date_str = request.GET.get("end_date")

        delivery_logs = DeliveryWebhookLog.objects.all()

        # Filtro padrão: apenas se nenhum outro filtro for fornecido
        if not any([message_id, webhook_status, start_date_str, end_date_str]):
            today = timezone.now().date()
            delivery_logs = delivery_logs.filter(created_at__date=today)
            start_date = today.strftime("%Y-%m-%d")
            end_date = today.strftime("%Y-%m-%d")
        else:
            start_date = start_date_str or ""
            end_date = end_date_str or ""

        if message_id:
            delivery_logs = delivery_logs.filter(message_id__icontains=message_id)
        if webhook_status:
            delivery_logs = delivery_logs.filter(webhook_status=webhook_status)
        if start_date:
            delivery_logs = delivery_logs.filter(created_at__date__gte=start_date)
        if end_date:
            delivery_logs = delivery_logs.filter(created_at__date__lte=end_date)

        # Estatísticas Delivery (baseadas nos filtros)
        total_callbacks = delivery_logs.count()
        success_callbacks = delivery_logs.filter(webhook_status="success").count()
        not_found_callbacks = delivery_logs.filter(webhook_status="not_found").count()
        forward_error_callbacks = delivery_logs.filter(
            webhook_status="forward_error"
        ).count()
        invalid_payload_callbacks = delivery_logs.filter(
            webhook_status="invalid_payload"
        ).count()
        last_callback = delivery_logs.order_by("-created_at").first()
        last_callback_time = (
            last_callback.created_at.strftime("%d/%m/%Y %H:%M:%S")
            if last_callback
            else "-"
        )
        avg_time = delivery_logs.filter(processing_time_ms__isnull=False).aggregate(
            models.Avg("processing_time_ms")
        )["processing_time_ms__avg"]
        avg_time_formatted = f"{int(avg_time)} ms" if avg_time else "-"

        paginator = Paginator(delivery_logs.order_by("-created_at"), 20)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context = {
            "active_tab": "delivery",
            "stats": {
                "total_callbacks": total_callbacks,
                "success_callbacks": success_callbacks,
                "not_found_callbacks": not_found_callbacks,
                "forward_error_callbacks": forward_error_callbacks,
                "invalid_payload_callbacks": invalid_payload_callbacks,
                "last_callback": last_callback_time,
                "avg_time": avg_time_formatted,
            },
            "delivery_logs": page_obj,
            "message_id": message_id,
            "webhook_status": webhook_status,
            "start_date": start_date,
            "end_date": end_date,
            "is_paginated": page_obj.has_other_pages(),
            "page_obj": page_obj,
        }
    else:  # active_tab == "api"
        # Nova lógica para ApiRequestLog
        carga_number = request.GET.get("carga_number", "")
        request_status = request.GET.get("request_status", "")
        response_status = request.GET.get("response_status", "")
        token_id = request.GET.get("token", "")
        start_date_str = request.GET.get("start_date")
        end_date_str = request.GET.get("end_date")

        api_logs = ApiRequestLog.objects.all()

        # Filtro padrão: apenas se nenhum outro filtro for fornecido
        if not any(
            [
                carga_number,
                request_status,
                response_status,
                token_id,
                start_date_str,
                end_date_str,
            ]
        ):
            today = timezone.now().date()
            api_logs = api_logs.filter(created_at__date=today)
            start_date = today.strftime("%Y-%m-%d")
            end_date = today.strftime("%Y-%m-%d")
        else:
            start_date = start_date_str or ""
            end_date = end_date_str or ""

        if carga_number:
            api_logs = api_logs.filter(carga_number__icontains=carga_number)
        if request_status:
            api_logs = api_logs.filter(request_status=request_status)
        if response_status:
            api_logs = api_logs.filter(response_status=response_status)
        if token_id:
            api_logs = api_logs.filter(api_token_id=token_id)
        if start_date:
            api_logs = api_logs.filter(created_at__date__gte=start_date)
        if end_date:
            api_logs = api_logs.filter(created_at__date__lte=end_date)

        # Estatísticas API (baseadas nos filtros)
        total_requests = api_logs.count()
        success_requests = api_logs.filter(request_status="success").count()
        failed_requests = api_logs.exclude(request_status="success").count()
        unique_ips = api_logs.values("ip_address").distinct().count()
        avg_time = api_logs.filter(processing_time_ms__isnull=False).aggregate(
            models.Avg("processing_time_ms")
        )["processing_time_ms__avg"]
        last_request = api_logs.order_by("-created_at").first()
        last_request_time = (
            last_request.created_at.strftime("%d/%m/%Y %H:%M:%S")
            if last_request
            else "-"
        )

        # Tokens disponíveis para filtro
        available_tokens = ApiToken.objects.filter(is_active=True).order_by("name")

        paginator = Paginator(api_logs.order_by("-created_at"), 20)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context = {
            "active_tab": "api",
            "stats": {
                "total_requests": total_requests,
                "success_requests": success_requests,
                "failed_requests": failed_requests,
                "unique_ips": unique_ips,
                "avg_time": round(avg_time, 2) if avg_time else 0,
                "last_request": last_request_time,
            },
            "api_logs": page_obj,
            "carga_number": carga_number,
            "request_status": request_status,
            "response_status": response_status,
            "token_id": token_id,
            "start_date": start_date,
            "end_date": end_date,
            "available_tokens": available_tokens,
            "is_paginated": page_obj.has_other_pages(),
            "page_obj": page_obj,
        }

    return render(request, "dashboard.html", context)


def index(request):
    return render(request, "index.html")


def _sanitize_carga_number(carga_number: str) -> str:
    """
    Sanitiza o número da carga para prevenir SQL injection e outros ataques.
    Remove todos os caracteres que não sejam dígitos.
    """
    if not carga_number:
        return ""

    # Remove todos os caracteres que não sejam dígitos
    sanitized = re.sub(r"[^\d]", "", str(carga_number))

    # Limita o tamanho para evitar ataques de buffer overflow
    return sanitized[:20] if sanitized else ""


def _extract_content_from_response(response_text: str, content_type: str = "") -> str:
    """
    Extrai a mensagem da chave 'msg' do JSON retornado pelo sistema externo.
    """
    try:
        json_data = json.loads(response_text)
        return str(json_data.get("msg", "Resposta sem mensagem"))
    except json.JSONDecodeError as e:
        logger.error(f"Erro ao parsear JSON da resposta: {e}")
        return "Erro ao processar resposta do sistema externo"


def _process_carga_response(response_text: str) -> dict:
    """
    Processa a resposta do sistema interno e retorna formato padronizado.

    Retorna:
        {"status": "0", "message": ""} - Quando carga não encontrada
        {"status": "1", "message": "..."} - Quando carga encontrada
    """
    # Extrair mensagem usando função existente
    message = _extract_content_from_response(response_text)

    # Verificar se é mensagem de erro (carga não encontrada)
    if "Verificar o número da carga informado" in message:
        return {"status": "0", "message": ""}

    # Retornar mensagem normal
    return {"status": "1", "message": message}


@require_http_methods(["GET", "POST"])
def consulta_status_carga(request):
    """
    View para consulta de status de carga no sistema externo.
    Não requer autenticação conforme solicitado.
    """
    context = {
        "carga_number": "",
        "status_response": "",
        "error_message": "",
        "success": False,
    }

    if request.method == "POST":
        carga_number = request.POST.get("carga_number", "").strip()

        if not carga_number:
            context["error_message"] = "Por favor, informe o número da carga."
            return render(request, "consulta_status_carga.html", context)

        # Sanitizar o número da carga
        sanitized_carga = _sanitize_carga_number(carga_number)

        if not sanitized_carga:
            context["error_message"] = "Número da carga inválido. Use apenas números."
            return render(request, "consulta_status_carga.html", context)

        # Verificar se a URL está configurada
        carga_status_url = getattr(settings, "CARGA_STATUS_URL", "")
        if not carga_status_url:
            context["error_message"] = (
                "Serviço de consulta não configurado. Entre em contato com o administrador."
            )
            logger.error("CARGA_STATUS_URL não configurada no settings")
            return render(request, "consulta_status_carga.html", context)

        try:
            # Construir URLs para fallback (adiciona o número da carga em cada URL)
            base_urls = carga_status_url.rstrip("/")
            # Se tiver múltiplas URLs, adicionar o número da carga em cada uma
            urls_with_carga = ",".join(
                [f"{url.rstrip('/')}/{sanitized_carga}" for url in base_urls.split(",")]
            )
            timeout = getattr(settings, "CARGA_STATUS_TIMEOUT", 10)

            logger.info(f"Consultando status da carga {sanitized_carga}")

            # Fazer a requisição com sistema de fallback
            response = try_urls_with_cache(
                urls_string=urls_with_carga,
                method="GET",
                timeout=timeout,
                cache_key="carga_status",
                cache_timeout=300,  # 5 minutos
                headers={
                    "User-Agent": "Tambasa-Webhook/1.0",
                    "Accept": "text/plain, text/html, */*",
                },
            )

            if response.status_code == 200:
                # Extrai o conteúdo relevante da resposta
                content_type = response.headers.get("content-type", "")
                clean_response = _extract_content_from_response(
                    response.text, content_type
                )

                context["status_response"] = clean_response
                context["success"] = True
                context["carga_number"] = sanitized_carga
                logger.info(
                    f"Consulta de carga {sanitized_carga} realizada com sucesso"
                )
            else:
                context["error_message"] = (
                    f"Erro na consulta: HTTP {response.status_code}"
                )
                logger.warning(
                    f"Erro na consulta da carga {sanitized_carga}: HTTP {response.status_code}"
                )

        except requests.exceptions.Timeout:
            context["error_message"] = (
                "Timeout na consulta. Tente novamente em alguns instantes."
            )
            logger.error(f"Timeout na consulta da carga {sanitized_carga}")

        except requests.exceptions.ConnectionError:
            context["error_message"] = (
                "Erro de conexão com o serviço. Tente novamente mais tarde."
            )
            logger.error(f"Erro de conexão na consulta da carga {sanitized_carga}")

        except requests.exceptions.RequestException as e:
            context["error_message"] = "Erro interno na consulta. Tente novamente."
            logger.error(
                f"Erro na requisição para consulta da carga {sanitized_carga}: {e}"
            )

        except Exception as e:
            context["error_message"] = (
                "Erro interno do sistema. Entre em contato com o suporte."
            )
            logger.error(f"Erro inesperado na consulta da carga {sanitized_carga}: {e}")

    return render(request, "consulta_status_carga.html", context)


def _get_client_ip(request: HttpRequest) -> str:
    """
    Obtém o IP real do cliente, considerando proxies.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def _validate_api_token(request: HttpRequest) -> tuple[bool, Optional[ApiToken]]:
    """
    Valida o token de autenticação do header Authorization.

    Returns:
        (is_valid, token_obj)
    """
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return False, None

    token_value = auth_header.replace("Bearer ", "").strip()

    if not token_value:
        return False, None

    try:
        token = ApiToken.objects.get(token=token_value, is_active=True)
        # Atualizar último uso
        token.last_used = timezone.now()
        token.save(update_fields=["last_used"])
        return True, token
    except ApiToken.DoesNotExist:
        return False, None


@csrf_exempt
@require_http_methods(["GET"])
@ratelimit(key="header:authorization", rate="60/m", method="GET", block=False)
def api_consulta_carga(request: HttpRequest, carga_number: str) -> JsonResponse:
    """
    API endpoint para consulta de status de carga.

    Autenticação: Bearer token no header Authorization
    Rate limit: 60 requisições por minuto por token

    Retorna:
        200: {"status": "0"|"1", "message": "..."}
        400: {"error": "mensagem de erro"}
        401: {"error": "Token inválido ou ausente"}
        429: {"error": "Rate limit excedido"}
        503: {"error": "Serviço indisponível"}
    """
    _cleanup_old_api_requests()  # Limpeza de logs antigos
    start_time = time.time()
    ip_address = _get_client_ip(request)

    # Verificar rate limit
    if getattr(request, "limited", False):
        logger.warning(f"Rate limit excedido para IP {ip_address}")
        ApiRequestLog.objects.create(
            ip_address=ip_address,
            carga_number=carga_number[:20],
            request_status="rate_limited",
            processing_time_ms=int((time.time() - start_time) * 1000),
        )
        return JsonResponse(
            {"error": "Rate limit excedido. Tente novamente em alguns instantes."},
            status=429,
        )

    # Validar token
    is_valid, token_obj = _validate_api_token(request)
    if not is_valid:
        logger.warning(f"Tentativa de acesso com token inválido - IP: {ip_address}")
        ApiRequestLog.objects.create(
            ip_address=ip_address,
            carga_number=carga_number[:20],
            request_status="invalid_token",
            processing_time_ms=int((time.time() - start_time) * 1000),
        )
        return JsonResponse({"error": "Token inválido ou ausente"}, status=401)

    # Sanitizar número da carga
    sanitized_carga = _sanitize_carga_number(carga_number)

    if not sanitized_carga:
        logger.warning(f"Número de carga inválido: {carga_number} - IP: {ip_address}")
        ApiRequestLog.objects.create(
            ip_address=ip_address,
            api_token=token_obj,
            carga_number=carga_number[:20],
            request_status="invalid_input",
            processing_time_ms=int((time.time() - start_time) * 1000),
        )
        return JsonResponse(
            {"error": "Número da carga inválido. Use apenas números."}, status=400
        )

    # Verificar se URL está configurada
    carga_status_url = getattr(settings, "CARGA_STATUS_URL", "")
    if not carga_status_url:
        logger.error("CARGA_STATUS_URL não configurada")
        ApiRequestLog.objects.create(
            ip_address=ip_address,
            api_token=token_obj,
            carga_number=sanitized_carga,
            request_status="system_error",
            processing_time_ms=int((time.time() - start_time) * 1000),
        )
        return JsonResponse(
            {"error": "Serviço de consulta não configurado"}, status=503
        )

    try:
        # Construir URLs para fallback (adiciona o número da carga em cada URL)
        base_urls = carga_status_url.rstrip("/")
        # Se tiver múltiplas URLs, adicionar o número da carga em cada uma
        urls_with_carga = ",".join(
            [f"{url.rstrip('/')}/{sanitized_carga}" for url in base_urls.split(",")]
        )
        timeout = getattr(settings, "CARGA_STATUS_TIMEOUT", 10)

        logger.info(
            f"API: Consultando carga {sanitized_carga} - Token: {token_obj.name} - IP: {ip_address}"
        )

        # Fazer requisição com sistema de fallback
        response = try_urls_with_cache(
            urls_string=urls_with_carga,
            method="GET",
            timeout=timeout,
            cache_key="carga_status_api",
            cache_timeout=300,  # 5 minutos
            headers={
                "User-Agent": "Webhook-API/1.0",
                "Accept": "application/json, text/plain, */*",
            },
        )

        if response.status_code == 200:
            # Processar resposta
            processed_response = _process_carga_response(response.text)

            # Registrar log de sucesso
            processing_time = int((time.time() - start_time) * 1000)
            ApiRequestLog.objects.create(
                ip_address=ip_address,
                api_token=token_obj,
                carga_number=sanitized_carga,
                request_status="success",
                response_status=processed_response["status"],
                response_message=processed_response["message"],
                internal_system_status_code=response.status_code,
                internal_system_response=response.text[:500],
                processing_time_ms=processing_time,
            )

            logger.info(
                f"API: Consulta bem-sucedida - Carga: {sanitized_carga} - "
                f"Status: {processed_response['status']} - Tempo: {processing_time}ms"
            )

            return JsonResponse(processed_response, status=200)
        else:
            # Erro HTTP do sistema interno
            logger.warning(
                f"API: Erro HTTP {response.status_code} do sistema interno - Carga: {sanitized_carga}"
            )
            ApiRequestLog.objects.create(
                ip_address=ip_address,
                api_token=token_obj,
                carga_number=sanitized_carga,
                request_status="system_error",
                internal_system_status_code=response.status_code,
                internal_system_response=response.text[:500],
                processing_time_ms=int((time.time() - start_time) * 1000),
            )
            return JsonResponse(
                {"error": "Erro ao consultar sistema interno"}, status=503
            )

    except requests.exceptions.Timeout:
        logger.error(f"API: Timeout na consulta - Carga: {sanitized_carga}")
        ApiRequestLog.objects.create(
            ip_address=ip_address,
            api_token=token_obj,
            carga_number=sanitized_carga,
            request_status="timeout",
            processing_time_ms=int((time.time() - start_time) * 1000),
        )
        return JsonResponse(
            {"error": "Timeout na consulta ao sistema interno"}, status=503
        )

    except requests.exceptions.ConnectionError:
        logger.error(f"API: Erro de conexão - Carga: {sanitized_carga}")
        ApiRequestLog.objects.create(
            ip_address=ip_address,
            api_token=token_obj,
            carga_number=sanitized_carga,
            request_status="connection_error",
            processing_time_ms=int((time.time() - start_time) * 1000),
        )
        return JsonResponse(
            {"error": "Erro de conexão com sistema interno"}, status=503
        )

    except Exception as e:
        logger.error(f"API: Erro inesperado - Carga: {sanitized_carga} - Erro: {e}")
        ApiRequestLog.objects.create(
            ip_address=ip_address,
            api_token=token_obj,
            carga_number=sanitized_carga,
            request_status="system_error",
            processing_time_ms=int((time.time() - start_time) * 1000),
        )
        return JsonResponse({"error": "Erro interno do sistema"}, status=500)
