from django import template
import requests
from io import BytesIO
from PIL import Image
import base64
from django.core.cache import cache
import logging

register = template.Library()
logger = logging.getLogger(__name__)


@register.filter
def proxy_image(url, size='300x450'):
    if not url:
        return ''

    # Кэширование результатов
    cache_key = f"proxy_image:{url}:{size}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    width, height = map(int, size.split('x'))

    try:
        # Оптимизация: таймаут 1с и сжатие JPEG вместо WebP
        response = requests.get(url, timeout=1, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code != 200:
            return url

        img = Image.open(BytesIO(response.content))

        # Автоматическое определение формата
        img_format = 'JPEG' if img.mode == 'RGB' else 'PNG'
        mime_type = 'image/jpeg' if img_format == 'JPEG' else 'image/png'

        # Ресайз только если необходимо
        if img.size != (width, height):
            img = img.resize((width, height), Image.LANCZOS)

        buffer = BytesIO()
        quality = 70 if img_format == 'JPEG' else 85
        img.save(buffer, format=img_format, quality=quality, optimize=True)

        img_str = base64.b64encode(buffer.getvalue()).decode()
        result = f"data:{mime_type};base64,{img_str}"

        # Кэширование на 24 часа
        cache.set(cache_key, result, 60 * 60 * 24)
        return result

    except Exception as e:
        logger.error(f"Image proxy error: {str(e)}", exc_info=True)
        return url