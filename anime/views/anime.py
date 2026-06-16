import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.db.models import Q, Prefetch, IntegerField, Func, F
from django.db.models.functions import Cast
from django.core.paginator import Paginator
from django.core.cache import cache
from django.utils import timezone
from ..models import Anime, Franchise, Comment
from ..forms import CommentForm
from ..templatetags.time_tags import natural_time

logger = logging.getLogger(__name__)

def anime_detail(request, pk, slug=None, slug_en=None):
    anime = get_object_or_404(Anime, pk=pk)
    
    # Определение канонического URL
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_yandex_bot = any(bot in user_agent for bot in ['yandexbot', 'yandexaccessibilitybot', 'yandexmobilebot'])
    is_google_bot = any(bot in user_agent for bot in ['googlebot', 'googlebot-video'])

    if is_yandex_bot:
        canonical_url = f"https://yamu.su{reverse('anime:anime_detail', kwargs={'pk': pk, 'slug': anime.slug})}"
    elif is_google_bot:
        canonical_url = f"https://yamu.su{reverse('anime:anime_detail_en', kwargs={'pk': pk, 'slug_en': anime.slug_en})}"
    else:
        if slug is not None:
            canonical_url = f"https://yamu.su{reverse('anime:anime_detail', kwargs={'pk': pk, 'slug': anime.slug})}"
        else:
            canonical_url = f"https://yamu.su{reverse('anime:anime_detail_en', kwargs={'pk': pk, 'slug_en': anime.slug_en})}"

    screenshots = anime.screenshots.all().order_by('order')[:5]
    selected_voice = request.GET.get('voice', 'ANILIBRIA')

    # Кэширование франшизы
    cache_key_franchise = f"anime_franchise_{anime.id}"
    franchise_parts = cache.get(cache_key_franchise)
    if franchise_parts is None:
        franchise = anime.franchise
        franchise_parts = list(franchise.get_anime_objects()) if franchise else []
        cache.set(cache_key_franchise, franchise_parts, 3600 * 24)

    # Кэширование похожих аниме
    cache_key_similar = f"anime_similar_{anime.id}"
    similar_anime = cache.get(cache_key_similar)
    if similar_anime is None:
        similar_anime = []
        if anime.genres:
            main_genres = [g.strip().lower() for g in anime.genres.split(',')]
            similar_query = Anime.objects.exclude(id=anime.id)
            
            franchise = anime.franchise
            if franchise and franchise.anime_ids:
                similar_query = similar_query.exclude(shikimori_id__in=franchise.anime_ids)

            # Исключаем не первые сезоны
            franchises = Franchise.objects.annotate(
                list_len=Cast(Func(F('anime_ids'), function='jsonb_array_length'), output_field=IntegerField())
            ).filter(list_len__gt=1).values_list('anime_ids', flat=True)

            exclude_non_first_ids = []
            for ids in franchises:
                exclude_non_first_ids.extend(ids[1:])
            
            if exclude_non_first_ids:
                exclude_non_first_set = set(str(sid) for sid in exclude_non_first_ids)
                similar_query = similar_query.exclude(shikimori_id__in=exclude_non_first_set)

            genre_q = Q()
            for genre in main_genres:
                genre_q |= Q(genres__icontains=genre)
            similar_query = similar_query.filter(genre_q)

            candidates = list(similar_query.order_by('-shikimori_rating')[:15])
            filtered_similar = []
            for item in candidates:
                item_genres = [g.strip().lower() for g in item.genres.split(',')]
                common = len(set(main_genres) & set(item_genres))
                if common >= 2:
                    filtered_similar.append(item)
                    if len(filtered_similar) >= 10: break
            
            similar_anime = filtered_similar
            cache.set(cache_key_similar, similar_anime, 3600 * 24)

    # Комментарии
    total_root_comments = Comment.objects.filter(anime=anime, parent__isnull=True).count()
    root_comments = Comment.objects.filter(anime=anime, parent__isnull=True).prefetch_related(
        Prefetch('replies', queryset=Comment.objects.all())
    ).order_by('-created_at')

    paginator = Paginator(root_comments, 10)
    page_number = request.GET.get('page', 1)
    comments_page = paginator.get_page(page_number)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and request.GET.get('type') == 'comments':
        loaded_count = comments_page.start_index() - 1
        remaining = max(total_root_comments - loaded_count - comments_page.object_list.count(), 0)
        return render(request, 'anime/comments_fragment.html', {
            'comments': comments_page,
            'total_comments': total_root_comments,
            'remaining': remaining
        })

    voices = {'ANILIBRIA': 'AniLibria', 'DREAMCAST': 'DreamCast', 'ANIDUB': 'AniDUB', 'SHIZA': 'Shiza Project'}

    context = {
        'anime': anime,
        'shikimori_id': anime.shikimori_id,
        'screenshots': screenshots,
        'voices': voices.items(),
        'franchise_parts': franchise_parts,
        'selected_voice': selected_voice,
        'comments': comments_page,
        'form': CommentForm(),
        'canonical_url': canonical_url,
        'total_comments': total_root_comments,
        'remaining': max(total_root_comments - comments_page.start_index() + 1 - comments_page.object_list.count(), 0),
        'similar_anime': similar_anime,
    }
    return render(request, 'anime/detail.html', context)

def anime_detail_redirect(request, pk):
    anime = get_object_or_404(Anime, pk=pk)
    return redirect('anime:anime_detail', pk=pk, slug=anime.slug, permanent=True)
