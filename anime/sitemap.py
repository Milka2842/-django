from django.contrib.sitemaps import Sitemap
from .models import Anime
from django.urls import reverse
from django.utils import timezone

class StaticSitemap(Sitemap):
    changefreq = "daily"
    priority = 1.0
    protocol = "https"

    def items(self):
        return ['anime:home', 'anime:top']

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        return timezone.localdate()

class AnimeSitemapRU(Sitemap):  # Для Яндекс (кириллические URL)
    changefreq = "daily"
    priority = 0.9
    protocol = "https"

    def items(self):
        return Anime.objects.all()

    def lastmod(self, obj):
        now = timezone.localtime(timezone.now())
        if obj.last_full_update:
            return timezone.localtime(obj.last_full_update).date()
        if obj.rating_last_updated:
            return timezone.localtime(obj.rating_last_updated).date()
        return now.date()

    def location(self, obj):
        return reverse('anime:anime_detail', kwargs={'pk': obj.pk, 'slug': obj.slug})

class AnimeSitemapEN(Sitemap):  # Для Google (английские URL)
    changefreq = "daily"
    priority = 0.9
    protocol = "https"

    def items(self):
        return Anime.objects.exclude(slug_en__isnull=True)

    def lastmod(self, obj):
        now = timezone.localtime(timezone.now())
        if obj.last_full_update:
            return timezone.localtime(obj.last_full_update).date()
        if obj.rating_last_updated:
            return timezone.localtime(obj.rating_last_updated).date()
        return now.date()

    def location(self, obj):
        return reverse('anime:anime_detail_en', kwargs={'pk': obj.pk, 'slug_en': obj.slug_en})







