from django.apps import AppConfig


class AnimeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'anime'

    # Уберите метод ready() или оставьте пустым
    def ready(self):
        pass
