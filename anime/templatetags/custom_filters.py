from django import template

register = template.Library()

@register.filter
def change_quality(url, quality):
    return url.replace('720', quality)

@register.filter
def force_http(url):
    """Принудительно преобразует URL к HTTP протоколу"""
    if url.startswith('https://'):
        return url.replace('https://', 'http://', 1)
    return url


@register.filter
def replace(value, arg):
    """
    Replaces a string with another string
    Usage: {{ value|replace:"old,new" }}
    """
    old, new = arg.split(',')
    return value.replace(old, new)