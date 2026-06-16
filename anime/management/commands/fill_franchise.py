from django.core.management.base import BaseCommand
from anime.models import Anime, Franchise

class Command(BaseCommand):
    help = 'Заполняет поле franchise в Anime на основе Franchise.anime_ids'

    def handle(self, *args, **options):
        self.stdout.write('Начинаем заполнение поля franchise...')

        franchises = Franchise.objects.all()
        updated_count = 0

        for franchise in franchises:
            for sid in franchise.anime_ids:
                try:
                    anime = Anime.objects.get(shikimori_id=str(sid))
                    if anime.franchise != franchise:
                        anime.franchise = franchise
                        anime.save(update_fields=['franchise'])
                        updated_count += 1
                        self.stdout.write(f'Обновлено: {anime.title} -> {franchise.name}')
                except Anime.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f'Аниме с shikimori_id {sid} не найдено'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Ошибка для {sid}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'Заполнение завершено. Обновлено {updated_count} записей.'))