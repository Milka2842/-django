import json
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from googleapiclient.discovery import build
from google.oauth2 import service_account
from ..models import BlockedDomain

logger = logging.getLogger(__name__)

from django.db.models import Q, Case, When, Value, FloatField, Func
from django.contrib.postgres.search import TrigramSimilarity
from django.urls import reverse
from django.shortcuts import get_object_or_404
from ..models import BlockedDomain, Anime

logger = logging.getLogger(__name__)

class Greatest(Func):
    function = 'GREATEST'
    arity = 2
    output_field = FloatField()

@require_http_methods(["GET"])
def get_blocked_domains(request):
    domains = list(BlockedDomain.objects.all().values_list('domain', flat=True))
    return JsonResponse(domains, safe=False)

def anime_search_api(request):
    try:
        query = request.GET.get('q', '').strip()
        if not query:
            return JsonResponse({'results': []})

        if len(query) > 10: threshold = 0.05
        elif len(query) > 5: threshold = 0.07
        elif len(query) > 3: threshold = 0.1
        else: threshold = 0.15

        results = Anime.objects.annotate(
            exact_match=Case(When(title__iexact=query, then=Value(1.0)), default=Value(0.0), output_field=FloatField()),
            prefix_match=Case(When(title__istartswith=query, then=Value(0.9)), default=Value(0.0), output_field=FloatField()),
            trigram_similarity=TrigramSimilarity('title', query)
        ).annotate(
            total_score=Greatest('exact_match', 'prefix_match', 'trigram_similarity')
        ).filter(
            Q(exact_match=1.0) | Q(prefix_match=0.9) | Q(trigram_similarity__gt=threshold)
        ).order_by('-total_score')[:15]

        data = []
        for anime in results:
            data.append({
                'id': anime.id,
                'title': anime.title,
                'poster': anime.poster_kodik or '/static/images/no-poster.png',
                'url': reverse('anime:anime_detail', kwargs={'pk': anime.id, 'slug': anime.slug}),
                'similarity': float(anime.total_score)
            })
        return JsonResponse({'results': data})
    except Exception as e:
        logger.error(f"Ошибка поиска: {str(e)}", exc_info=True)
        results = Anime.objects.filter(title__icontains=query)[:10]
        data = [{'id': a.id, 'title': a.title, 'poster': a.poster_kodik or '/static/images/no-poster.png',
                 'url': reverse('anime:anime_detail', kwargs={'pk': a.id, 'slug': a.slug})} for a in results]
        return JsonResponse({'results': data})

def get_kodik_url(request, pk):
    anime = get_object_or_404(Anime, pk=pk)
    episode = request.GET.get('episode', 1)
    voice = request.GET.get('voice', 'ANILIBRIA')
    kodik_url = f"https://kodik.cc/player.html?autoPlay=true&id={anime.shikimori_id}&episode={episode}&translation={voice}"
    return JsonResponse({'kodik_url': kodik_url})

def update_poster(request, pk):
    anime = get_object_or_404(Anime, pk=pk)
    poster_url = request.GET.get('poster')
    if poster_url:
        anime.poster_kodik = poster_url
        anime.save()
    return JsonResponse({"status": "success"})

@csrf_exempt
def send_to_indexing(request):
    if request.method == 'POST':
        url = request.POST.get('url')
        logger.info(f"Получен запрос на индексацию: {url}")

        try:
            credentials = service_account.Credentials.from_service_account_info(
                {
                    "type": "service_account",
                    "project_id": "yume-460120",
                    "private_key_id": "d6f622169a8e2e38332702302f0d1a3ecbfbabb7",
                    "private_key": settings.GOOGLE_INDEXING_PRIVATE_KEY,
                    "client_email": "yamu-444@yume-460120.iam.gserviceaccount.com",
                    "client_id": "106806926172966241709",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/yamu-444%40yume-460120.iam.gserviceaccount.com",
                    "universe_domain": "googleapis.com"
                },
                scopes=['https://www.googleapis.com/auth/indexing']
            )

            service = build('indexing', 'v3', credentials=credentials)
            body = {'url': url, 'type': 'URL_UPDATED'}
            response = service.urlNotifications().publish(body=body).execute()

            logger.info(f"Успешная индексация: {url}")
            return JsonResponse({'status': 'success', 'url': url})
        except Exception as e:
            logger.error(f"Ошибка индексации: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

@csrf_exempt
@require_POST
def add_blocked_domain(request):
    try:
        data = json.loads(request.body)
        domain = data.get('domain', '').strip().lower()

        if not domain:
            return JsonResponse({'success': False, 'error': 'No domain provided'})

        blocked_domain, created = BlockedDomain.objects.get_or_create(
            domain=domain,
            defaults={'source': 'auto_detected'}
        )

        return JsonResponse({
            'success': True,
            'domain': domain,
            'created': created
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})
