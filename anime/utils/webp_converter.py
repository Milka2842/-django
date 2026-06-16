import hashlib
from django.core.cache import cache


def convert_to_webp(image_url, save_path):
    """
    Конвертирует изображение по URL в WebP формат с кэшированием
    """
    # Создаем ключ кэша
    cache_key = f'webp_{hashlib.md5(image_url.encode()).hexdigest()}'

    # Проверяем кэш
    cached_path = cache.get(cache_key)
    if cached_path:
        return cached_path

    try:
        # Загружаем изображение
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()

        # Открываем как изображение
        img = Image.open(BytesIO(response.content))

        # Конвертируем в WebP
        output = BytesIO()

        if img.mode in ('RGBA', 'LA'):
            img.save(output, format='WEBP', quality=85, lossless=False)
        else:
            rgb_img = img.convert('RGB')
            rgb_img.save(output, format='WEBP', quality=85)

        output.seek(0)

        # Сохраняем результат
        webp_path = f"{os.path.splitext(save_path)[0]}.webp"
        default_storage.save(webp_path, ContentFile(output.read()))

        # Сохраняем в кэш на 24 часа
        cache.set(cache_key, webp_path, 86400)

        logger.info(f"Успешно сконвертировано: {image_url} -> {webp_path}")
        return webp_path

    except Exception as e:
        logger.error(f"Ошибка конвертации {image_url}: {str(e)}")
        return None