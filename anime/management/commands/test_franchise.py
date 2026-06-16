from django.core.management.base import BaseCommand
from anime.models import Anime, Franchise

class Command(BaseCommand):
    help = 'Тестирование системы франшиз'

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write("ТЕСТИРОВАНИЕ СИСТЕМЫ ФРАНШИЗ")
        self.stdout.write("=" * 80)

        # 1. Проверим общее количество франшиз и аниме
        total_franchises = Franchise.objects.count()
        total_anime = Anime.objects.count()
        anime_with_franchise_code = Anime.objects.filter(franchise_code__isnull=False).exclude(franchise_code='').count()

        self.stdout.write(f"Всего франшиз в БД: {total_franchises}")
        self.stdout.write(f"Всего аниме в БД: {total_anime}")
        self.stdout.write(f"Аниме со старым franchise_code: {anime_with_franchise_code}")
        self.stdout.write("")

        # 2. Возьмем первую франшизу и проверим её
        if total_franchises > 0:
            franchise = Franchise.objects.first()
            self.stdout.write(f"Тестируем франшизу: {franchise}")
            self.stdout.write(f"anime_ids: {franchise.anime_ids}")
            self.stdout.write(f"Тип данных anime_ids: {type(franchise.anime_ids)}")

            # Проверим каждый ID
            for i, sid in enumerate(franchise.anime_ids):
                self.stdout.write(f"  ID {i+1}: {sid} (тип: {type(sid)})")

                # Проверим, существует ли аниме с таким ID
                anime = Anime.objects.filter(shikimori_id=str(sid)).first()
                if anime:
                    self.stdout.write(f"    ✓ Найден аниме: {anime.title}")
                else:
                    self.stdout.write(f"    ✗ Аниме с ID {sid} НЕ НАЙДЕН!")

            # Протестируем get_anime_objects
            anime_objects = franchise.get_anime_objects()
            self.stdout.write(f"get_anime_objects() вернул: {len(anime_objects)} аниме")
            for anime in anime_objects:
                self.stdout.write(f"  - {anime.title} (ID: {anime.shikimori_id})")
        else:
            self.stdout.write("❌ Нет франшиз в БД!")
            return

        self.stdout.write("")

        # 3. Протестируем поиск франшизы для конкретного аниме
        self.stdout.write("ТЕСТИРОВАНИЕ ПОИСКА ФРАНШИЗЫ ДЛЯ АНИМЕ")
        self.stdout.write("-" * 50)

        # Возьмем первое аниме из франшизы
        if franchise.anime_ids:
            test_shikimori_id = str(franchise.anime_ids[0])
            self.stdout.write(f"Тестируем поиск для shikimori_id: {test_shikimori_id}")

            # Проверим аниме
            anime = Anime.objects.filter(shikimori_id=test_shikimori_id).first()
            if anime:
                self.stdout.write(f"Найден аниме: {anime.title}")

                # Попробуем найти франшизу разными способами
                self.stdout.write("Поиск франшизы:")

                # Способ 1: через contains
                found_franchise = Franchise.objects.filter(anime_ids__contains=[test_shikimori_id]).first()
                self.stdout.write(f"  anime_ids__contains=[{test_shikimori_id}]: {'✓ Найдена' if found_franchise else '✗ Не найдена'}")

                # Способ 2: через __in
                found_franchise2 = Franchise.objects.filter(anime_ids__contains=test_shikimori_id).first()
                self.stdout.write(f"  anime_ids__contains={test_shikimori_id}: {'✓ Найдена' if found_franchise2 else '✗ Не найдена'}")

                # Способ 3: проверим все франшизы вручную
                all_franchises = Franchise.objects.all()
                manual_found = None
                for f in all_franchises:
                    if test_shikimori_id in [str(x) for x in f.anime_ids]:
                        manual_found = f
                        break
                self.stdout.write(f"  Ручной поиск: {'✓ Найдена' if manual_found else '✗ Не найдена'}")

            else:
                self.stdout.write(f"❌ Аниме с shikimori_id {test_shikimori_id} не найден!")

        self.stdout.write("")
        self.stdout.write("=" * 80)
        self.stdout.write("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
        self.stdout.write("=" * 80)