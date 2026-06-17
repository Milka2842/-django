import os
import locale
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yume.settings')

# Устанавливаем локаль безопасно (если русская не поддерживается — используем английскую)
try:
    locale.setlocale(locale.LC_ALL, 'ru_RU.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_ALL, 'C')  # базовая локаль

application = get_wsgi_application()