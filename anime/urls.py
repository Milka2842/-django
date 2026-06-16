from django.urls import path
from .views import anime, catalog, api, comments
from django.conf import settings
from django.conf.urls.static import static
from .image_utils import webp_proxy

app_name = "anime"

urlpatterns = [
    # Anime Detail
    path("<int:pk>/<str:slug_en>/", anime.anime_detail, name="anime_detail_en"),
    path("<int:pk>/<str:slug>/", anime.anime_detail, name="anime_detail"),
    
    # Catalog
    path("", catalog.home, name="home"),
    path('top/', catalog.top_anime, name='top'),
    
    # Comments
    path('<int:pk>/comment/', comments.add_comment, name='add_comment'),
    path('comment/<int:comment_id>/like/', comments.like_comment, name='like_comment'),
    path('comment/<int:comment_id>/dislike/', comments.dislike_comment, name='dislike_comment'),
    
    # API
    path('api/search/', api.anime_search_api, name='anime_search_api'),
    path('api/blocked-domains/', api.get_blocked_domains, name='get_blocked_domains'),
    path('api/blocked-domains/add/', api.add_blocked_domain, name='add_blocked_domain'),
    path('api/indexing/', api.send_to_indexing, name='send_to_indexing'),
    
    # Utils
    path('images/webp/', webp_proxy, name='webp_proxy'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
