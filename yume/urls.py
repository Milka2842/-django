from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from anime.views import api as anime_api
from users.views import CustomLoginRedirectView
from django.contrib.sitemaps.views import sitemap
from django.views.generic.base import TemplateView
from anime.sitemap import StaticSitemap, AnimeSitemapRU, AnimeSitemapEN

sitemaps = {
    'static': StaticSitemap,
    'anime_ru': AnimeSitemapRU,
    'anime_en': AnimeSitemapEN,
}

# Отдельные sitemaps для разных поисковых систем
sitemaps_ru = {
    'static': StaticSitemap,
    'anime': AnimeSitemapRU,
}

sitemaps_en = {
    'static': StaticSitemap,
    'anime': AnimeSitemapEN,
}

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("anime.urls", namespace="anime")),  # Главная страница
    path("users/", include("users.urls")),
    path('robots.txt', TemplateView.as_view(
        template_name='robots.txt',
        content_type='text/plain'
    )),
    path('kodik.txt', serve, {
        'document_root': settings.BASE_DIR,
        'path': 'kodik.txt'
    }, name='kodik_txt'),
    path('admin/send-to-indexing/', anime_api.send_to_indexing, name='send_to_indexing'),
    path("accounts/login/", CustomLoginRedirectView.as_view()),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    # Отдельные sitemaps для разных поисковых систем
    path('sitemap_ru.xml', sitemap, {'sitemaps': sitemaps_ru}, name='sitemap_ru'),
    path('sitemap_en.xml', sitemap, {'sitemaps': sitemaps_en}, name='sitemap_en'),
]


if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)