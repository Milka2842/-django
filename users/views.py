import os
import secrets
from django.db import transaction
from googleapiclient.discovery import build
import requests
from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import authenticate, login
from django.contrib.auth.views import LogoutView
from django.contrib.auth import login as auth_login
from .models import CustomUser
from users.forms import CustomUserCreationForm
from django.views.generic import RedirectView
from django.urls import reverse_lazy
from django.contrib.auth import logout
import logging

logger = logging.getLogger(__name__)


def verify_recaptcha_v2(token):
    """Проверка reCAPTCHA v2"""
    if not token:
        return False

    data = {
        'secret': settings.RECAPTCHA_PRIVATE_KEY,
        'response': token
    }
    try:
        response = requests.post(
            'https://www.google.com/recaptcha/api/siteverify',
            data=data,
            timeout=5
        )
        result = response.json()
        return result.get('success', False)
    except Exception as e:
        logger.error(f"reCAPTCHA verification failed: {e}")
        return False

def profile_view(request):
    return render(request, 'users/profile.html')


def verify_email(request, user_id, token):
    user = get_object_or_404(CustomUser, pk=user_id)

    # Проверка токена и срока действия (24 часа)
    if (user.verification_token == token and
            (timezone.now() - user.token_created) < timedelta(hours=24)):
        user.email_verified = True
        user.save()
        return render(request, 'users/verification_success.html')

    return render(request, 'users/verification_failed.html')


def register_view(request):
    recaptcha_public_key = settings.RECAPTCHA_PUBLIC_KEY

    if request.method == 'POST':
        # Получение данных из формы
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        # Проверка reCAPTCHA
        recaptcha_response = request.POST.get('g-recaptcha-response')
        if not recaptcha_response or not verify_recaptcha_v2(recaptcha_response):
            return render(request, 'users/register.html', {
                'error': 'Пройдите проверку reCAPTCHA',
                'RECAPTCHA_PUBLIC_KEY': recaptcha_public_key
            })

        # Валидация данных
        errors = []
        if not all([username, email, password1, password2]):
            errors.append('Все поля обязательны для заполнения')
        if password1 != password2:
            errors.append('Пароли не совпадают')
        if len(password1) < 5:
            errors.append('Пароль должен содержать минимум 5 символов')
        if CustomUser.objects.filter(username=username).exists():
            errors.append('Имя пользователя уже занято')
        if CustomUser.objects.filter(email=email).exists():
            errors.append('Email уже используется')

        if errors:
            return render(request, 'users/register.html', {
                'error': '<br>'.join(errors),
                'RECAPTCHA_PUBLIC_KEY': recaptcha_public_key
            })

        try:
            # Создаем пользователя без сохранения в БД
            verification_code = secrets.randbelow(900000) + 100000
            user = CustomUser(
                username=username,
                email=email,
                is_active=False,
                verification_code=verification_code
            )
            user.set_password(password1)  # Хешируем пароль

            # Пытаемся отправить письмо
            send_mail(
                'Код подтверждения регистрации',
                f'Ваш код подтверждения: {verification_code}',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )

            # Если отправка успешна - сохраняем пользователя
            user.save()

            # Сохраняем ID пользователя в сессии
            request.session['verify_user_id'] = user.id
            return redirect('verify_code')

        except Exception as e:
            logger.error(f"Ошибка регистрации: {str(e)}")
            return render(request, 'users/register.html', {
                'error': f'Ошибка регистрации: {str(e)}',
                'RECAPTCHA_PUBLIC_KEY': recaptcha_public_key
            })

    return render(request, 'users/register.html', {
        'RECAPTCHA_PUBLIC_KEY': recaptcha_public_key
    })
def create_message(sender, to, link):
    import base64
    from email.mime.text import MIMEText
    message = MIMEText(f'Подтвердите почту: {link}')
    message['to'] = to
    message['from'] = sender
    message['subject'] = 'Подтверждение регистрации'
    return base64.urlsafe_b64encode(message.as_bytes()).decode()

def logout_view(request):
    logout(request)
    return redirect('anime:home')


def verify_code_view(request):
    user_id = request.session.get('verify_user_id')
    if not user_id:
        return redirect('register')

    try:
        user = CustomUser.objects.get(pk=user_id)
    except CustomUser.DoesNotExist:
        return redirect('register')

    if request.method == 'POST':
        code = request.POST.get('code')

        if str(user.verification_code) == str(code):
            # Активируем пользователя только после подтверждения
            user.is_active = True
            user.save()

            # Автоматический вход
            login(request, user)
            return redirect('anime:home')
        else:
            return render(request, 'users/verify_code.html', {
                'error': 'Неверный код подтверждения. Проверьте письмо.'
            })

    return render(request, 'users/verify_code.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        # Пытаемся аутентифицировать по username
        user = authenticate(request, username=username, password=password)

        # Если не получилось, пробуем по email
        if user is None:
            try:
                user_by_email = CustomUser.objects.get(email=username)
                user = authenticate(request, username=user_by_email.username, password=password)
            except CustomUser.DoesNotExist:
                pass

        if user is not None:
            if user.is_active:
                login(request, user)
                return redirect(settings.LOGIN_REDIRECT_URL)
            else:
                return render(request, 'users/login.html', {
                    'error': 'Ваш аккаунт не активирован. Проверьте почту для получения кода подтверждения.'
                })
        else:
            return render(request, 'users/login.html', {
                'error': 'Неверное имя пользователя или пароль.'
            })

    return render(request, 'users/login.html')


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('anime:home')

class CustomLoginRedirectView(RedirectView):
    pattern_name = 'login'
    query_string = True