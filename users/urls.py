from django.urls import path
from .views import register_view , verify_code_view, profile_view, verify_email, login_view, logout_view

urlpatterns = [
    path('register/', register_view, name='register'),
    path('profile/', profile_view, name='profile'),
    path('verify/<int:user_id>/<str:token>/', verify_email, name='verify_email'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('verify-code/', verify_code_view, name='verify_code'),
]