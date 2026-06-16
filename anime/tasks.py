import httpx
import json
import logging
from django.conf import settings
from celery import shared_task
import jwt
from datetime import datetime, timedelta
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

from anime import models

logger = logging.getLogger(__name__)


@shared_task
def convert_new_images_to_webp():
    """
    Задача для конвертации новых изображений в WebP
    """
    # Находим аниме без WebP версий
    animes_without_webp = Anime.objects.filter(poster_webp__isnull=True)

    for anime in animes_without_webp:
        if anime.poster_kodik:
            convert_to_webp(
                anime.poster_kodik,
                f"posters/{anime.id}/poster"
            )

@shared_task
def update_ratings_task():
    """Задача для обновления рейтингов порциями с логированием изменений"""
    from anime.models import Anime
    from django.conf import settings

    # Размер пачки из настроек
    batch_size = getattr(settings, 'RATING_UPDATE_BATCH_SIZE', 15)
    updated = Anime.update_ratings_batch(batch_size)

    if updated:
        print("\n" + "=" * 50)
        print(f"Обновлены рейтинги для {len(updated)} аниме:")
        print("-" * 50)
        for item in updated:
            print(f"[ID: {item['id']}] {item['title']}")
            print(f"    Рейтинг: {item['old']} → {item['new']}")
        print("=" * 50 + "\n")
    else:
        print("Рейтинги не изменились для текущей пачки аниме")

    return f"Обновлено: {len(updated)} аниме"

@shared_task
def ping():
    logger.info("PING: Worker is alive")
    return "pong"

@shared_task
def update_ongoing_anime():
    """Обновление онгоинг-аниме каждые 6 часов"""
    from anime.models import Anime
    from django.utils import timezone
    import time
    import logging
    from random import randint

    logger = logging.getLogger(__name__)

    logger.info("=" * 50)
    logger.info("ЗАПУЩЕНА ЗАДАЧА ОБНОВЛЕНИЯ ОНГОИНГ-АНИМЕ!")
    logger.info("=" * 50)

    # Находим аниме со статусом "ongoing"
    ongoing_animes = Anime.objects.filter(status='ongoing')
    updated_count = 0


    for anime in ongoing_animes:
        try:
            if not anime.genres or (not anime.description and not anime.description_manual):
                anime.get_data_from_shikimori()
                anime.update_from_kodik()
                anime.update_poster_from_kodik()
            else:
                # Иначе только критически важные данные
                anime.update_from_kodik()  # Количество эпизодов
                anime.update_shikimori_rating(force=True)

            # Сохраняем все изменения
            anime.last_full_update = timezone.now()
            anime.save()
            updated_count += 1

            logger.info(f"Обновлено онгоинг-аниме: {anime.title} (ID: {anime.id})")

            # Случайная задержка между 0.5 и 2.5 секунд для снижения нагрузки
            time.sleep(0.5 + randint(0, 2000) / 1000)

        except Exception as e:
            logger.error(f"Ошибка обновления онгоинг-аниме {anime.title}: {str(e)}", exc_info=True)

    return f"Обновлено {updated_count} онгоинг-аниме"


@shared_task
def submit_to_google_indexing(url, anime_id=None):
    """Асинхронная задача для отправки URL на индексацию в Google"""
    try:
        # Получаем access token для Google
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": create_google_jwt_token()
        }

        token_response = httpx.post(token_url, data=token_data)
        token_response.raise_for_status()
        access_token = token_response.json()["access_token"]

        # Отправляем на индексацию
        indexing_url = "https://indexing.googleapis.com/v3/urlNotifications:publish"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "url": url,
            "type": "URL_UPDATED"
        }

        indexing_response = httpx.post(indexing_url, headers=headers, json=payload)
        indexing_response.raise_for_status()

        logger.info(f"Google indexing success for {url}")

        # Обновляем время индексации в модели, если передан anime_id
        if anime_id:
            from anime.models import Anime
            from django.utils import timezone
            Anime.objects.filter(pk=anime_id).update(last_indexed_at=timezone.now())

        return True

    except Exception as e:
        logger.error(f"Google indexing failed: {str(e)}")
        return False


def create_google_jwt_token():
    """Создаем JWT токен для Google"""
    private_key = settings.GOOGLE_INDEXING_PRIVATE_KEY
    service_account_email = "yamu-444@yume-460120.iam.gserviceaccount.com"

    now = datetime.utcnow()
    payload = {
        "iss": service_account_email,
        "sub": service_account_email,
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + timedelta(hours=1),
        "scope": "https://www.googleapis.com/auth/indexing"
    }

    # Загружаем приватный ключ
    private_key_pem = serialization.load_pem_private_key(
        private_key.encode('utf-8'),
        password=None,
        backend=default_backend()
    )

    return jwt.encode(
        payload,
        private_key_pem,
        algorithm="RS256",
        headers={"kid": "d6f622169a8e2e38332702302f0d1a3ecbfbabb7"}
    )


@shared_task
def update_incomplete_anime():
    """Обновление аниме с отсутствующими данными раз в 24 часа"""
    from anime.models import Anime
    from django.utils import timezone
    from datetime import timedelta
    import logging

    logger = logging.getLogger(__name__)
    logger.info("Запуск задачи для аниме с неполными данными")

    # Находим аниме без жанров или описания, которые не обновлялись более 24 часов
    incomplete_animes = Anime.objects.filter(
        models.Q(genres__isnull=True) |
        models.Q(genres='') |
        # Исключаем ручные описания из условия обновления
        (models.Q(description__isnull=True) & ~models.Q(description_manual=True)) |
        (models.Q(description='') & ~models.Q(description_manual=True))
    ).exclude(
        last_full_update__gt=timezone.now() - timedelta(hours=23)
    )

    updated_count = 0

    for anime in incomplete_animes:
        try:
            # Всегда обновляем, но description_manual защитит ручное описание
            anime.get_data_from_shikimori()
            anime.update_from_kodik()
            anime.update_poster_from_kodik()

            # Сохраняем с обновлением времени
            anime.last_full_update = timezone.now()
            anime.save()
            updated_count += 1

            # Проверяем, остались ли еще недостающие данные
            still_incomplete = not anime.genres or not anime.description
            logger.info(f"Аниме {'все еще' if still_incomplete else 'теперь'} полное: {anime.title}")

        except Exception as e:
            logger.error(f"Ошибка обновления неполного аниме {anime.title}: {str(e)}")

    result = f"Обновлено {updated_count} аниме с неполными данными"
    logger.info(result)
    return result

def submit_to_yandex(url):
    """Отправка на индексацию в Яндекс"""
    try:
        # Получаем токен из настроек
        yandex_token = settings.YANDEX_OAUTH_TOKEN
        if not yandex_token:
            logger.warning("Yandex OAuth token not configured")
            return False

        # Получаем ID пользователя и хоста
        user_id = get_yandex_user_id(yandex_token)
        if not user_id:
            return False

        host_id = get_yandex_host_id(yandex_token, user_id)
        if not host_id:
            return False

        # Отправляем URL на индексацию
        api_url = f"https://api.webmaster.yandex.net/v4/user/{user_id}/hosts/{host_id}/recrawl/queue"
        headers = {
            "Authorization": f"OAuth {yandex_token}",
            "Content-Type": "application/json"
        }
        payload = {"url": url}

        response = httpx.post(api_url, headers=headers, json=payload)

        # Успешный ответ: 202 Accepted
        if response.status_code == 202:
            logger.info(f"Yandex indexing submitted for {url}")
            return True

        logger.error(f"Yandex indexing failed: {response.status_code} - {response.text}")
        return False

    except Exception as e:
        logger.error(f"Yandex indexing exception: {str(e)}")
        return False


def get_yandex_user_id(token):
    """Получаем ID пользователя Яндекс.Вебмастера"""
    try:
        response = httpx.get(
            "https://api.webmaster.yandex.net/v4/user",
            headers={"Authorization": f"OAuth {token}"}
        )

        if response.status_code == 200:
            data = response.json()
            return data.get("user_id")

        logger.error(f"Failed to get Yandex user ID: {response.status_code} - {response.text}")
        return None

    except Exception as e:
        logger.error(f"Error getting Yandex user ID: {str(e)}")
        return None


def get_yandex_host_id(token, user_id):
    """Получаем ID хоста (сайта) в Яндекс.Вебмастере"""
    try:
        response = httpx.get(
            f"https://api.webmaster.yandex.net/v4/user/{user_id}/hosts",
            headers={"Authorization": f"OAuth {token}"}
        )

        if response.status_code == 200:
            hosts = response.json().get("hosts", [])
            for host in hosts:
                # Ищем наш домен
                if host.get("unicode_host") == settings.SITE_DOMAIN:
                    return host.get("host_id")

        logger.error(f"Host not found in Yandex Webmaster: {settings.SITE_DOMAIN}")
        return None

    except Exception as e:
        logger.error(f"Error getting Yandex host ID: {str(e)}")
        return None