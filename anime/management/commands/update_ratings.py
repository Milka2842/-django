from django.core.management.base import BaseCommand
from anime.models import Anime

class Command(BaseCommand):
    help = 'Ежедневное обновление рейтингов'

    def handle(self, *args, **options):
        for anime in Anime.objects.all():
            anime.update_shikimori_rating(force=True)
            self.stdout.write(f"Рейтинг обновлен: {anime.title}")