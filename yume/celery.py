import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yume.settings')

app = Celery('yume')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


@app.task
def cleanup_old_tasks():
    from celery.result import AsyncResult
    from django.utils import timezone
    from datetime import timedelta

    # Удаляем задачи старше 24 часов
    old_tasks = AsyncResult.iterall()
    for task in old_tasks:
        if task.date_done and task.date_done < timezone.now() - timedelta(hours=24):
            task.forget()