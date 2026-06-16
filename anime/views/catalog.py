import logging
from django.shortcuts import render
from django.db.models import Q
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.utils import timezone
from django.core.cache import cache
from datetime import datetime
from ..models import Anime

logger = logging.getLogger(__name__)

def get_current_season():
    month = timezone.now().month
    if month in [12, 1, 2]: return 'winter'
    elif month in [3, 4, 5]: return 'spring'
    elif month in [6, 7, 8]: return 'summer'
    else: return 'autumn'

def get_previous_season():
    current_season = get_current_season()
    seasons = ['winter', 'spring', 'summer', 'autumn']
    current_index = seasons.index(current_season)
    previous_index = (current_index - 1) % 4
    return seasons[previous_index]

def home(request):
    # --- ОПТИМИЗАЦИЯ: Кэширование главной страницы ---
    cache_key = "home_page_data"
    context = cache.get(cache_key)

    if context is None:
        trending_anime = Anime.objects.filter(
            season__in=[get_current_season(), get_previous_season()],
            year__in=[timezone.now().year, timezone.now().year - 1]
        ).only('id', 'title', 'poster_kodik', 'shikimori_rating', 'season', 'year', 'slug')[:20]

        popular_genres = [
            'боевик', 'драма', 'комедия', 'повседневность',
            'приключения', 'романтика', 'сёнен', 'фэнтези', 'экшен',
            'школа', 'мелодрама'
        ]

        genre_sections = []
        for genre in popular_genres:
            anime_list = Anime.objects.filter(
                genres__icontains=genre
            ).only('id', 'title', 'poster_kodik', 'shikimori_rating', 'season', 'year', 'slug')[:10]

            genre_sections.append({
                'genre': genre.capitalize(),
                'anime_list': anime_list
            })

        context = {
            'trending_anime': trending_anime,
            'genre_sections': genre_sections,
        }
        # Кэшируем на 1 час
        cache.set(cache_key, context, 3600)

    return render(request, 'anime/home.html', context)

def top_anime(request):
    queryset = Anime.objects.exclude(shikimori_rating__isnull=True)
    selected_genres = request.GET.getlist('genres')

    if selected_genres:
        query = Q()
        for genre in selected_genres:
            query &= Q(genres__contains=genre.strip())
        queryset = queryset.filter(query)

    year_min = request.GET.get('year_min')
    year_max = request.GET.get('year_max')
    if year_min and year_min.isdigit():
        queryset = queryset.filter(year__gte=int(year_min))
    if year_max and year_max.isdigit():
        queryset = queryset.filter(year__lte=int(year_max))

    sort = request.GET.get('sort', '-shikimori_rating')
    if sort == '-shikimori_rating':
        queryset = queryset.order_by('-shikimori_rating', 'id')
    elif sort == 'shikimori_rating':
        queryset = queryset.order_by('shikimori_rating', 'id')
    elif sort == '-year':
        queryset = queryset.order_by('-year', 'id')
    elif sort == 'year':
        queryset = queryset.order_by('year', 'id')
    else:
        queryset = queryset.order_by('-shikimori_rating', 'id')

    paginator = Paginator(queryset, 20)
    page = request.GET.get('page', 1)

    try:
        top_list = paginator.page(page)
    except PageNotAnInteger:
        top_list = paginator.page(1)
    except EmptyPage:
        top_list = paginator.page(paginator.num_pages)

    # Получаем данные для фильтров, чтобы страница не была пустой
    genres = cache.get('all_genres_list')
    if not genres:
        try:
            from ..models import Genre
            genres = list(Genre.objects.values_list('name', flat=True).order_by('name'))
            if genres:
                cache.set('all_genres_list', genres, 3600 * 24)
        except Exception:
            genres = ['боевик', 'драма', 'комедия', 'повседневность', 'приключения', 'романтика', 'сёнен', 'фэнтези']

    context = {
        'top_list': top_list,
        'genres': genres,
        'selected_genres': selected_genres,
        'current_year': timezone.now().year,
    }

    return render(request, 'anime/top.html', context)
