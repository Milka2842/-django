from django import template
from django.urls import reverse
from urllib.parse import quote
import hashlib

register = template.Library()

@register.filter
def to_webp_lqip(url):
    """Возвращает URL на мини-версию постера для LQIP (ширина 20px)"""
    if not url:
        return ''
    # Путь к твоему прокси
    proxy_url = reverse('anime:webp_proxy')
    return f"{proxy_url}?url={url}&width=20&quality=30"

@register.filter
def to_webp(image_url):
    """
    Фильтр для преобразования URL изображения в WebP версию
    """
    if not image_url:
        return image_url

    # Для внешних изображений используем наш прокси
    if image_url.startswith('http'):
        # Создаем хеш URL для кэширования
        url_hash = hashlib.md5(image_url.encode()).hexdigest()[:12]

        # Формируем URL к нашему обработчику WebP с указанием namespace
        try:
            proxy_url = reverse('anime:webp_proxy') + f"?url={quote(image_url)}&hash={url_hash}"
            return proxy_url
        except:
            # Если reverse не работает, возвращаем оригинальный URL
            return image_url

    # Для локальных файлов просто меняем расширение
    if '.' in image_url:
        base, ext = image_url.rsplit('.', 1)
        if ext.lower() in ['jpg', 'jpeg', 'png']:
            return f"{base}.webp"

    return image_url