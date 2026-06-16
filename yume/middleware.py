import logging

logger = logging.getLogger(__name__)

class DebugHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        logger.debug(f"Secure: {request.is_secure()}, Proto: {request.META.get('HTTP_X_FORWARDED_PROTO')}")
        return response


class BlockAdsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['X-Ad-Blocker'] = 'active'
        return response

class SEOHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Устанавливаем общие SEO-заголовки
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'SAMEORIGIN'

        # Специальные заголовки для sitemap
        if request.path == '/sitemap.xml':
            response['Content-Type'] = 'application/xml; charset=utf-8'
            response['Cache-Control'] = 'public, max-age=86400'  # Кешировать 24 часа

        return response


class BlockSitemapMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        path = request.path

        # Блокировка sitemap для Yandex
        if 'yandex' in user_agent:
            if path in ['/sitemap.xml', '/sitemap_en.xml']:
                return HttpResponseForbidden()

        return self.get_response(request)