class SearchEngineMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()

        # Более точное определение Яндекс бота
        request.is_yandex_bot = any([
            'yandex' in user_agent,
            'yandexbot' in user_agent,
            'yandexaccessibility' in user_agent
        ])

        # Более точное определение Google бота
        request.is_google_bot = any([
            'googlebot' in user_agent,
            'google' in user_agent and 'bot' in user_agent
        ])

        response = self.get_response(request)
        return response