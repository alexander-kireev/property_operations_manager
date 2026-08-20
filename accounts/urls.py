from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("registration_pending/", views.registration_pending_view, name="registration_pending"),
    path("confirm/<str:token>/", views.confirm_registration_view, name="confirm_registration")
]