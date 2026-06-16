from django.shortcuts import HttpResponse
from django.views.decorators.cache import cache_control
from django.core.cache import cache
from io import BytesIO
from PIL import Image
import requests
import hashlib
import logging

logger = logging.getLogger('image_utils')


@cache_control(max_age=86400 * 30)
def webp_proxy(request):
    image_url = request.GET.get('url')
    if not image_url:
        return HttpResponse(status=400)

    # Проверяем поддержку WebP браузером
    accept_header = request.META.get('HTTP_ACCEPT', '')
    supports_webp = 'image/webp' in accept_header

    # Если браузер не поддерживает WebP, перенаправляем на оригинал
    if not supports_webp:
        from django.shortcuts import redirect
        return redirect(image_url)

    # Ключ для кэша
    cache_key = hashlib.md5(f"webp_{image_url}".encode()).hexdigest()

    # Пытаемся получить из кэша
    cached_image = cache.get(cache_key)
    if cached_image:
        response = HttpResponse(cached_image, content_type='image/webp')
        response['X-Image-Cache'] = 'HIT'
        return response

    try:
        # Загружаем изображение
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()
        image_data = response.content

        # Конвертируем в WebP
        img = Image.open(BytesIO(image_data))
        output = BytesIO()

        if img.mode in ('RGBA', 'LA'):
            img.save(output, format='WEBP', lossless=False, quality=85)
        else:
            rgb_img = img.convert('RGB')
            rgb_img.save(output, format='WEBP', quality=85)

        webp_data = output.getvalue()

        # Сохраняем в кэш
        cache.set(cache_key, webp_data, 86400 * 30)

        response = HttpResponse(webp_data, content_type='image/webp')
        response['X-Image-Cache'] = 'MISS'
        return response

    except Exception as e:
        logger.error(f"Ошибка обработки изображения {image_url}: {str(e)}")
        # В случае ошибки перенаправляем на оригинал
        from django.shortcuts import redirect
        return redirect(image_url)