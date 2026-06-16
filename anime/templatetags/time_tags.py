from django import template
from django.utils import timezone
import humanize

register = template.Library()

@register.filter(name='natural_time')
def natural_time(value):
    humanize.i18n.activate("ru_RU")
    now = timezone.now()
    delta = now - value

    if delta.total_seconds() < 60:
        return "только что"
    if delta.days == 1:
        return "вчера"
    return humanize.naturaltime(delta)
