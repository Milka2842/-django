from django.core.management.base import BaseCommand
from anime.models import Anime, Screenshot
from anime.utils.webp_converter import convert_to_webp


class Command(BaseCommand):
    help = 'Конвертирует все изображения в WebP формат'

    def handle(self, *args, **options):
        # Конвертируем постеры аниме
        for anime in Anime.objects.all():
            if anime.poster_kodik:
                self.stdout.write(f"Конвертируем постер для {anime.title}")
                webp_path = convert_to_webp(
                    anime.poster_kodik,
                    f"posters/{anime.id}/poster"
                )

        # Конвертируем скриншоты
        for screenshot in Screenshot.objects.all():
            if screenshot.url:
                self.stdout.write(f"Конвертируем скриншот {screenshot.id}")
                webp_path = convert_to_webp(
                    screenshot.url,
                    f"screenshots/{screenshot.anime.id}/{screenshot.id}"
                )

        self.stdout.write(self.style.SUCCESS('Конвертация завершена'))