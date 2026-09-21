from django.urls import path, reverse_lazy
from . import views
from django.contrib.auth import views as auth_views

from .forms import PasswordResetConfirmForm

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("registration_pending/", views.registration_pending_view, name="registration_pending"),
    path("confirm/<str:token>/", views.confirm_registration_view, name="confirm_registration"),
    path("profile/", views.profile_page_view, name="profile_page"),
    path("change_email/", views.change_email_view, name="change_email"),
    path("change_password/", views.change_password_view, name="change_password"),
    path("delete_account/", views.delete_account_view, name="delete_account"),
    path("password/reset/email/", views.reset_password_protected_view, name="reset_password_protected"),
    path(
        "password/reset/<uidb64>/<token>/",
        views.PasswordResetConfirmPRGView.as_view(
            template_name="accounts/password_reset_confirm.html",
            form_class=PasswordResetConfirmForm,
            success_url=reverse_lazy("accounts:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "password/reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
]
