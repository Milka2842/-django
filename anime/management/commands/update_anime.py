from django.core.management.base import BaseCommand
from anime.models import Anime

class Command(BaseCommand):
    help = 'Updates anime data from API'

    def handle(self, *args, **options):
        anime, created = Anime.objects.get_or_create(id=1)
        if anime.update_episodes():
            self.stdout.write("Данные успешно обновлены!")
        else:
            self.stdout.write("Ошибка при обновлении данных")