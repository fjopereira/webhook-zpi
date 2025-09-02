import json
import logging

from django.conf import settings
from django.http import HttpRequest, JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
# from django_ratelimit.decorators import ratelimit  # Temporariamente desabilitado
from django.shortcuts import render
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from datetime import date

from .models import MessageLog
from django.core.paginator import Paginator
import requests


logger = logging.getLogger(__name__)


def _url_token_is_valid(url_token: str) -> bool:
    expected = getattr(settings, 'ZAPI_WEBHOOK_URL_TOKEN', '')
    return bool(expected) and url_token == expected


@csrf_exempt
@require_http_methods(["POST"])
# @ratelimit(key='ip', rate='100/m', method='POST', block=True)  # Temporariamente desabilitado
def zapi_on_message_received(request: HttpRequest, url_token: str) -> HttpResponse:
    if not _url_token_is_valid(url_token):
        logger.warning('Invalid URL token for Z-API webhook')
        return JsonResponse({'detail': 'Invalid token'}, status=401)

    content_type = request.headers.get('Content-Type', '')
    if 'application/json' not in content_type:
        return JsonResponse({'detail': 'Unsupported Media Type'}, status=415)

    try:
        body_bytes = request.body or b''
        payload = json.loads(body_bytes.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    # Log only text messages; ignore other message kinds
    text_block = payload.get('text') if isinstance(payload, dict) else None
    if isinstance(text_block, dict) and 'message' in text_block:
        is_group = payload.get('isGroup', False)
        message_id = payload.get('messageId', '')
        phone = payload.get('phone', '')
        message = text_block.get('message', '')
        broadcast = text_block.get('broadcast', False)
        
        # Save to database
        try:
            message_log = MessageLog.objects.create(
                is_group=is_group,
                message_id=message_id,
                phone=phone,
                message=message,
                broadcast=broadcast,
                external_system_status='pending'
            )
            logger.info(f"Message saved to database: {message_id}")
        except Exception as e:
            logger.error(f"Error saving message to database: {e}")
            return JsonResponse({'detail': 'Database error'}, status=500)
        
        # Forward data to another system
        try:
            forward_data = {
                'is_group': is_group,
                'message_id': message_id,
                'phone': phone,
                'message': message,
                'broadcast': broadcast
            }
            
            response = requests.post(
                settings.EXTERNAL_SYSTEM_URL,
                json=forward_data,
                timeout=settings.EXTERNAL_SYSTEM_TIMEOUT
            )
            
            # Update database with forwarding results
            if response.status_code == 200:
                message_log.external_system_status = 'success'
                message_log.external_system_response = response.text[:500]  # Limit response size
                message_log.external_system_status_code = response.status_code
                message_log.forwarded_at = timezone.now()
                logger.info(f"Data forwarded successfully to external system: {message_id}")
            else:
                message_log.external_system_status = 'failed'
                message_log.external_system_response = f"HTTP {response.status_code}: {response.text[:500]}"
                message_log.external_system_status_code = response.status_code
                message_log.forwarded_at = timezone.now()
                logger.warning(f"Failed to forward data to external system. Status: {response.status_code}, Response: {response.text}")
            
            # Save the updated record
            message_log.save()
                
        except requests.exceptions.RequestException as e:
            # Update database with error information
            message_log.external_system_status = 'failed'
            message_log.external_system_response = f"Network error: {str(e)[:500]}"
            message_log.forwarded_at = timezone.now()
            message_log.save()
            logger.error(f"Error forwarding data to external system: {e}")
        
        # Simple console logging
        print(f"Z-API text received | isGroup={is_group} | messageId={message_id} | phone={phone} | message='{message}' | broadcast={broadcast}")

    # Return success response
    return JsonResponse({'status': 'ok'}, status=200)


@require_http_methods(["GET"])
def healthz(request: HttpRequest) -> HttpResponse:
    return JsonResponse({'status': 'ok'}, status=200)


@login_required
def dashboard(request):
    phone = request.GET.get('phone', '')
    status = request.GET.get('status', '')
    is_group = request.GET.get('is_group', '')
    broadcast = request.GET.get('broadcast', '')
    start_date = request.GET.get('start_date') or date.today().strftime('%Y-%m-%d')
    end_date = request.GET.get('end_date') or date.today().strftime('%Y-%m-%d')

    messages = MessageLog.objects.all()

    # Filtro padrão: mensagens do dia atual se nenhum filtro for passado
    if not (phone or status or start_date or end_date or is_group or broadcast):
        today = timezone.now().date()
        messages = messages.filter(created_at__date=today)

    if phone:
        messages = messages.filter(phone__icontains=phone)
    if status:
        messages = messages.filter(external_system_status=status)
    if start_date:
        messages = messages.filter(created_at__date__gte=start_date)
    if end_date:
        messages = messages.filter(created_at__date__lte=end_date)
    if is_group != '':
        messages = messages.filter(is_group=(is_group == 'true'))
    if broadcast != '':
        messages = messages.filter(broadcast=(broadcast == 'true'))

    # Estatísticas
    total_messages = MessageLog.objects.count()
    unique_contacts = MessageLog.objects.values('phone').distinct().count()
    groups = MessageLog.objects.filter(is_group=True).count()
    forwarded = MessageLog.objects.filter(external_system_status='forwarded').count()
    failed = MessageLog.objects.filter(external_system_status='failed').count()
    last_message = MessageLog.objects.order_by('-created_at').first()
    last_message_time = last_message.created_at.strftime('%d/%m/%Y %H:%M') if last_message else '-'

    # Paginação
    paginator = Paginator(messages.order_by('-created_at'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'stats': {
            'total_messages': total_messages,
            'unique_contacts': unique_contacts,
            'groups': groups,
            'forwarded': forwarded,
            'failed': failed,
            'last_message': last_message_time,
        },
        'messages': page_obj,
        'phone': phone,
        'status': status,
        'start_date': start_date,
        'end_date': end_date,
        'is_group': is_group,
        'broadcast': broadcast,
        'is_paginated': page_obj.has_other_pages(),
        'page_obj': page_obj,
    }
    return render(request, 'dashboard.html', context)


def index(request):
    return render(request, 'index.html')

