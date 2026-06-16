from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings
import requests
import logging
from django.db import transaction
from django.contrib.sites.models import Site
from django.urls import reverse
from model_utils import FieldTracker
from transliterate import translit
logger = logging.getLogger(__name__)
from dateutil.parser import parse
import re
from celery import shared_task

class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)

@shared_task
def send_to_google_indexing_task(url):
    try:
        from googleapiclient.discovery import build
        from google.oauth2 import service_account
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"Начата индексация: {url}")

        credentials = service_account.Credentials.from_service_account_info(
            {
                "type": "service_account",
                "project_id": "yume-460120",
                "private_key_id": "d6f622169a8e2e38332702302f0d1a3ecbfbabb7",
                "private_key": settings.GOOGLE_INDEXING_PRIVATE_KEY,
                "client_email": "yamu-444@yume-460120.iam.gserviceaccount.com",
                "client_id": "106806926172966241709",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/yamu-444%40yume-460120.iam.gserviceaccount.com",
                "universe_domain": "googleapis.com"
            },
            scopes=['https://www.googleapis.com/auth/indexing']
        )

        service = build('indexing', 'v3', credentials=credentials)
        body = {'url': url, 'type': 'URL_UPDATED'}
        response = service.urlNotifications().publish(body=body).execute()

        logger.info(f"Успешная индексация: {url}")
        return True
    except Exception as e:
        logger.error(f"Ошибка индексации: {str(e)}")
        return False


class BlockedDomain(models.Model):
    domain = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=100, default='auto_detected')  # auto_detected или manual

    def __str__(self):
        return self.domain

    class Meta:
        indexes = [
            models.Index(fields=['domain']),
        ]
        ordering = ['-created_at']

class Anime(models.Model):
    description_manual = models.BooleanField(
        default=False,
        verbose_name="Описание изменено вручную",
        help_text="Если отмечено, автоматическое обновление не будет перезаписывать описание"
    )
    rating_last_updated = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Последнее обновление рейтинга"
    )
    poster_webp = models.ImageField(
        upload_to='posters/webp/',
        blank=True,
        null=True,
        verbose_name="WebP постер"
    )
    slug = models.SlugField(
        max_length=255,
        blank=True,
        verbose_name="ЧПУ-метка",
        help_text="Автоматически генерируется из названия",
        allow_unicode=True  # Разрешаем Unicode-символы (кириллицу)
    )
    shikimori_rating = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Рейтинг Shikimori"
    )

    tracker = FieldTracker(fields=['title', 'slug', 'status', 'slug_en'])

    title = models.CharField(max_length=255, default='Без названия')
    description = models.TextField(blank=True)
    genres = models.CharField(max_length=255, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)

    shikimori_id = models.CharField(
        max_length=255,
        verbose_name="Shikimori ID",
        help_text="ID из URL Shikimori (пример: https://shikimori.one/animes/505 → 505)",
        unique=True  # Делаем уникальным, так как теперь основной идентификатор
    )
    franchise_code = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Код франшизы (например: SoloLeveling2)",
        help_text="Название франшизы + число для порядка. Пример: SoloLeveling1"
    )

    poster_kodik = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="Постер от Kodik"
    )


    SEASON_CHOICES = [
        ('winter', 'Зима'),
        ('spring', 'Весна'),
        ('summer', 'Лето'),
        ('autumn', 'Осень'),
    ]
    season = models.CharField(
        max_length=10,
        choices=SEASON_CHOICES,
        blank=True,
        null=True,
        verbose_name="Сезон выпуска"
    )

    STATUS_CHOICES = [
        ('anons', 'Анонсировано'),
        ('ongoing', 'Выходит'),
        ('released', 'Завершено'),
    ]
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='released',
        verbose_name="Статус"
    )

    franchise = models.ForeignKey(
        'Franchise',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Франшиза"
    )

    # Добавим поле для отслеживания последнего обновления
    last_full_update = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Последнее полное обновление"
    )


    def get_franchise_parts(self):
        """Возвращает все части франшизы в правильном порядке"""
        if not self.franchise_code:
            return []

        # Извлекаем базовое название (без цифр в конце)
        base_name = ''.join([c for c in self.franchise_code if not c.isdigit()]).strip()

        return Anime.objects.filter(
            franchise_code__startswith=base_name
        ).extra(
            select={'order': 'CAST(SUBSTRING(franchise_code FROM \'\\d+$\') AS INTEGER)'}
        ).order_by('order')

    def _shikimori_proxy_request(self, max_retries=None, base_delay=1, backoff=2):
        """
        Выполняет запрос к Shikimori через прокси yamu.su/shikimori.
        404 – сразу выбрасывает исключение (не повторяет).
        Остальные ошибки – повторяет бесконечно (если max_retries не задан).
        """
        import time
        import requests
        attempt = 0
        delay = base_delay
        while True:
            try:
                url = f"https://yamu.su/shikimori/api/animes/{self.shikimori_id}"
                headers = {"User-Agent": "AnimeSite/1.0 (contact@yamu.su)"}
                resp = requests.get(url, headers=headers, timeout=30, verify=False)
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    raise  # не повторяем
                if max_retries is not None and attempt >= max_retries:
                    raise
                logger.warning(f"HTTP error {e.response.status_code}: {e}. Retry in {delay}s")
                time.sleep(delay)
                attempt += 1
                delay *= backoff
            except Exception as e:
                if max_retries is not None and attempt >= max_retries:
                    raise
                logger.warning(f"Request error: {e}. Retry in {delay}s (attempt {attempt+1})")
                time.sleep(delay)
                attempt += 1
                delay *= backoff

    def update_shikimori_rating(self, force=False):
        from django.utils import timezone
        if not force and self.rating_last_updated:
            if (timezone.now() - self.rating_last_updated).total_seconds() < 86400:
                return
        try:
            data = self._shikimori_proxy_request()
            self.shikimori_rating = data.get('score')
            self.rating_last_updated = timezone.now()
            self.save(update_fields=['shikimori_rating', 'rating_last_updated'])
        except Exception as e:
            logger.error(f"Rating update error: {e}")


    total_episodes = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Количество эпизодов"
    )

    def get_season_display(self):
        return dict(self.SEASON_CHOICES).get(self.season, '')

    def generate_slug(self):
        """Генерирует русскоязычный слаг из названия"""
        # Используем русское название из Shikimori
        title = self.title.strip()

        # Заменяем пробелы на подчеркивания
        slug = title.replace(' ', '_')

        # Удаляем все символы, кроме букв, цифр и подчеркиваний
        slug = re.sub(r'[^\wа-яА-ЯёЁ]', '', slug, flags=re.UNICODE)

        # Ограничиваем длину
        return slug[:250]

    def update_poster_from_kodik(self):
        """Устанавливает постер со smarthard.net (без запросов к Shikimori)."""
        if not self.shikimori_id:
            return
        new_poster = f"https://smarthard.net/static/animes/{self.shikimori_id}.avif"
        if self.poster_kodik != new_poster:
            self.poster_kodik = new_poster
            self.save(update_fields=["poster_kodik"])
            logger.info(f"Постер для {self.title} ({self.shikimori_id}) обновлён на {new_poster}")

    def update_from_kodik(self):
        if not self.shikimori_id:
            logger.warning("Shikimori ID отсутствует. Обновление невозможно.")
            return

        data = self._shikimori_proxy_request()

        self.title = data.get('russian') or data.get('name') or self.title
        self.status = data.get('status', 'released')
        genres = [genre['russian'] for genre in data.get('genres', [])]
        self.genres = ", ".join(genres)

        aired_on = data.get('aired_on')
        if aired_on:
            try:
                self.year = int(aired_on[:4])
            except (ValueError, TypeError):
                pass

        self.total_episodes = data.get('episodes')

        if aired_on and len(aired_on) >= 7:
            try:
                month = int(aired_on[5:7])
                if 1 <= month <= 3:
                    self.season = 'winter'
                elif 4 <= month <= 6:
                    self.season = 'spring'
                elif 7 <= month <= 9:
                    self.season = 'summer'
                elif 10 <= month <= 12:
                    self.season = 'autumn'
            except (ValueError, IndexError):
                pass

        description = data.get('description', '')
        if description and not self.description_manual:
            import re
            clean_desc = re.sub(r'<[^>]+>', '', description)
            clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()
            self.description = clean_desc

        from django.utils import timezone
        self.last_full_update = timezone.now()
        self.save(update_fields=[
            'title', 'status', 'genres', 'year', 'total_episodes',
            'season', 'description', 'last_full_update'
        ])
        logger.info(f"Anime {self.title} updated via proxy from Shikimori")

    last_indexed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Последняя отправка на индексацию"
    )

    def get_absolute_url(self):
        return reverse('anime:anime_detail', kwargs={'pk': self.pk, 'slug': self.slug})

    slug_en = models.SlugField(
        max_length=255,
        blank=True,
        null=True,  # Разрешаем временно null
        verbose_name="English Slug",
        help_text="Automatically generated from English title",
        allow_unicode=False
    )

    def generate_en_slug(self):
        """Генерирует английский слаг из названия"""
        # Транслитерация кириллицы в латиницу
        try:
            slug = translit(self.title, 'ru', reversed=True)
        except:
            slug = self.title.encode('ascii', 'ignore').decode('ascii')

        slug = slug.strip().replace(' ', '_')
        slug = re.sub(r'[^\w]', '', slug)  # Удаляем не-алфавитные символы
        return slug.lower()[:250]

    def get_data_from_shikimori(self):
        """Получает название, статус и жанры через прокси Shikimori."""
        if not self.shikimori_id:
            return
        data = self._shikimori_proxy_request()
        self.title = data.get('russian') or data.get('name') or self.title
        self.status = data.get('status', 'released')
        genres = [genre['russian'] for genre in data.get('genres', [])]
        self.genres = ", ".join(genres)
        from django.utils import timezone
        self.last_full_update = timezone.now()
        self.save(update_fields=['title', 'status', 'genres', 'last_full_update'])

    def get_base_franchise_name(self):
        """Возвращает название франшизы без номера"""
        if not self.franchise_code:
            return ""
        return ''.join([c for c in self.franchise_code if not c.isdigit()]).strip()

    @classmethod
    def update_ratings_batch(cls, batch_size=10):
        """Обновляет рейтинг для пачки аниме с выводом изменений"""
        from django.utils import timezone
        from random import randint
        import time

        # Находим аниме с самым старым обновлением рейтинга
        animes = cls.objects.order_by('rating_last_updated')[:batch_size]
        updated_anime = []  # Для хранения информации об обновлениях

        for anime in animes:
            try:
                old_rating = anime.shikimori_rating
                # Случайная задержка от 0.5 до 2 секунд между запросами
                delay = 0.5 + randint(0, 1500) / 1000
                time.sleep(delay)

                # Сохраняем старое значение перед обновлением
                anime.update_shikimori_rating()
                new_rating = anime.shikimori_rating

                # Если рейтинг изменился
                if old_rating != new_rating:
                    updated_anime.append({
                        'id': anime.id,
                        'title': anime.title,
                        'old': old_rating,
                        'new': new_rating
                    })

                # Обновляем время последнего обновления
                anime.rating_last_updated = timezone.now()
                anime.save(update_fields=['shikimori_rating', 'rating_last_updated'])

            except Exception as e:
                logger.error(f"Ошибка обновления рейтинга для {anime.title}: {str(e)}")

        return updated_anime

    def save(self, *args, **kwargs):
        from django.utils import timezone
        from anime.tasks import submit_to_google_indexing
        from model_utils import FieldTracker

        # Инициализируем трекер полей
        if not hasattr(self, 'tracker'):
            self.tracker = FieldTracker(fields=['title', 'slug', 'status', 'slug_en'])

        is_new = self.pk is None
        was_ongoing = False

        # Для новых объектов: временные слаги и базовое сохранение
        if is_new:
            # Устанавливаем временные значения для слагов
            self.slug = "temp-slug"
            self.slug_en = "temp-slug-en"

            user_description = self.description if self.description else None

            # Первое сохранение чтобы получить ID
            super().save(*args, **kwargs)

            try:
                # Обновляем данные из внешних источников
                self.update_shikimori_rating(force=True)
                self.get_data_from_shikimori()
                self.update_from_kodik()
                self.update_poster_from_kodik()

                # Генерируем постоянные слаги после получения данных
                self.slug = self.generate_slug()
                self.slug_en = self.generate_en_slug()

                # Проверяем уникальность русскоязычного слага
                base_slug = self.slug
                counter = 1
                while Anime.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                    self.slug = f"{base_slug}_{counter}"
                    counter += 1

                # Проверяем уникальность англоязычного слага
                base_slug_en = self.slug_en
                counter_en = 1
                while Anime.objects.filter(slug_en=self.slug_en).exclude(pk=self.pk).exists():
                    self.slug_en = f"{base_slug_en}_{counter_en}"
                    counter_en += 1

                # Сохраняем все обновленные поля
                update_fields = [
                    'title', 'description', 'genres', 'year',
                    'season', 'total_episodes', 'poster_kodik',
                    'slug', 'slug_en',  # Обновляем оба слага
                    'shikimori_rating', 'rating_last_updated'
                ]
                super().save(update_fields=update_fields)

                # Отправка на индексацию
                if not settings.DEBUG:
                    full_url = f"https://yamu.su{reverse('anime:anime_detail_en', kwargs={'pk': self.pk, 'slug_en': self.slug_en})}"
                    submit_to_google_indexing.delay(full_url, self.pk)

                if user_description:
                    self.description = user_description
                    self.description_manual = True
            except Exception as e:
                logger.error(f"Ошибка при инициализации: {str(e)}", exc_info=True)
                raise
        else:
            # Для существующих объектов

            # Генерируем slug_en если он отсутствует
            if not self.slug_en:
                self.slug_en = self.generate_en_slug()
                base_slug = self.slug_en
                counter = 1
                while Anime.objects.filter(slug_en=self.slug_en).exclude(pk=self.pk).exists():
                    self.slug_en = f"{base_slug}_{counter}"
                    counter += 1

            # Запоминаем предыдущий статус
            try:
                old_instance = Anime.objects.get(pk=self.pk)
                was_ongoing = old_instance.status == 'ongoing'
            except Anime.DoesNotExist:
                pass

            # Обновляем рейтинг и сохраняем
            self.update_shikimori_rating()
            super().save(*args, **kwargs)

            # Определяем нужно ли отправлять на индексацию
            should_index = False
            if (self.tracker.has_changed('title') or
                    self.tracker.has_changed('slug') or
                    self.tracker.has_changed('slug_en') or
                    self.tracker.has_changed('status')):
                should_index = True

            # Для онгоингов - проверяем ежедневное обновление
            if self.status == 'ongoing' and (not was_ongoing or
                                             (not self.last_indexed_at or
                                              (timezone.now() - self.last_indexed_at).total_seconds() > 86400)):
                should_index = True

            # Отправка на индексацию
            if should_index and not settings.DEBUG:
                full_url = f"https://yamu.su{reverse('anime:anime_detail_en', kwargs={'pk': self.pk, 'slug_en': self.slug_en})}"
                submit_to_google_indexing.delay(full_url, self.pk)

class Franchise(models.Model):
    """Модель для хранения франшиз аниме как списков shikimori_id"""
    name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Название франшизы",
        help_text="Опционально, для удобства отображения"
    )
    anime_ids = models.JSONField(
        default=list,
        verbose_name="Список shikimori_id аниме",
        help_text="Список ID в правильном порядке, например: [123, 321, 456]"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Франшиза"
        verbose_name_plural = "Франшизы"
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['anime_ids']),
        ]

    def __str__(self):
        return self.name or f"Франшиза #{self.id}"

    def get_anime_objects(self):
        """Возвращает объекты Anime в порядке anime_ids"""
        if not self.anime_ids:
            return []
        anime_dict = {
            anime.shikimori_id: anime 
            for anime in Anime.objects.filter(shikimori_id__in=[str(sid) for sid in self.anime_ids])
        }
        # Сохраняем порядок из anime_ids
        return [anime_dict.get(str(sid)) for sid in self.anime_ids if str(sid) in anime_dict]

    def clean(self):
        if self.anime_ids:
            # Приводим все ID к строкам и удаляем пробелы
            str_ids = [str(sid).strip() for sid in self.anime_ids]
            existing = set(Anime.objects.filter(shikimori_id__in=str_ids).values_list('shikimori_id', flat=True))
            existing_str = {str(eid).strip() for eid in existing}
            invalid = set(str_ids) - existing_str
            if invalid:
                raise ValidationError(
                    f"Следующие shikimori_id не существуют: {invalid}"
                )

class Screenshot(models.Model):
    anime = models.ForeignKey(Anime, on_delete=models.CASCADE, related_name='screenshots')
    url = models.URLField(max_length=500)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Screenshot {self.order} for {self.anime.title}"

class Comment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    anime = models.ForeignKey(Anime, on_delete=models.CASCADE, related_name='comments')
    text = models.TextField()
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='replies'  # Должно совпадать с именем в queryset
    )
    created_at = models.DateTimeField(auto_now_add=True)
    likes = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='liked_comments', blank=True)
    dislikes = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='disliked_comments', blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.text[:20]}"



