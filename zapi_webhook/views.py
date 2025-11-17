import json
import logging
import re
from typing import Optional
from django_ratelimit.decorators import ratelimit
import time
from .models import ApiToken, ApiRequestLog

from django.conf import settings
from django.http import HttpRequest, JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import render
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from datetime import date, timedelta
from django.db import models

from .models import MessageLog
from django.core.paginator import Paginator
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


def _url_token_is_valid(url_token: str) -> bool:
    expected = getattr(settings, "ZAPI_WEBHOOK_URL_TOKEN", "")
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

            response = requests.post(
                settings.EXTERNAL_SYSTEM_URL,
                json=forward_data,
                timeout=settings.EXTERNAL_SYSTEM_TIMEOUT,
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
        start_date = request.GET.get("start_date") or date.today().strftime("%Y-%m-%d")
        end_date = request.GET.get("end_date") or date.today().strftime("%Y-%m-%d")
        message_id = request.GET.get("message_id", "")

        messages = MessageLog.objects.all()

        if not (phone or status or start_date or end_date or is_group or broadcast):
            today = timezone.now().date()
            messages = messages.filter(created_at__date=today)
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

        # Estatísticas MessageLog
        total_messages = MessageLog.objects.count()
        unique_contacts = MessageLog.objects.values("phone").distinct().count()
        groups = MessageLog.objects.filter(is_group=True).count()
        forwarded = MessageLog.objects.filter(
            external_system_status="forwarded"
        ).count()
        failed = MessageLog.objects.filter(external_system_status="failed").count()
        last_message = MessageLog.objects.order_by("-created_at").first()
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
    else:  # active_tab == "api"
        # Nova lógica para ApiRequestLog
        carga_number = request.GET.get("carga_number", "")
        request_status = request.GET.get("request_status", "")
        response_status = request.GET.get("response_status", "")
        token_id = request.GET.get("token", "")
        start_date = request.GET.get("start_date") or date.today().strftime("%Y-%m-%d")
        end_date = request.GET.get("end_date") or date.today().strftime("%Y-%m-%d")

        api_logs = ApiRequestLog.objects.all()

        # Filtro padrão: requisições do dia atual
        if not (carga_number or request_status or response_status or token_id):
            today = timezone.now().date()
            api_logs = api_logs.filter(created_at__date=today)

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

        # Estatísticas API
        total_requests = ApiRequestLog.objects.count()
        success_requests = ApiRequestLog.objects.filter(
            request_status="success"
        ).count()
        failed_requests = ApiRequestLog.objects.exclude(
            request_status="success"
        ).count()
        unique_ips = ApiRequestLog.objects.values("ip_address").distinct().count()
        avg_time = ApiRequestLog.objects.filter(
            processing_time_ms__isnull=False
        ).aggregate(models.Avg("processing_time_ms"))["processing_time_ms__avg"]
        last_request = ApiRequestLog.objects.order_by("-created_at").first()
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
            # Construir a URL completa
            full_url = f"{carga_status_url.rstrip('/')}/{sanitized_carga}"
            timeout = getattr(settings, "CARGA_STATUS_TIMEOUT", 10)

            logger.info(
                f"Consultando status da carga {sanitized_carga} na URL: {full_url}"
            )

            # Fazer a requisição para o sistema externo
            response = requests.get(
                full_url,
                timeout=timeout,
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
        # Construir URL e fazer requisição
        full_url = f"{carga_status_url.rstrip('/')}/{sanitized_carga}"
        timeout = getattr(settings, "CARGA_STATUS_TIMEOUT", 10)

        logger.info(
            f"API: Consultando carga {sanitized_carga} - Token: {token_obj.name} - IP: {ip_address}"
        )

        response = requests.get(
            full_url,
            timeout=timeout,
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
