from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required

from .forms import PendingRegistrationForm, EmailAuthenticationForm

from .models import PendingRegistration, User

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

from django.core import signing
from django.db import transaction

from .tokens import create_confirmation_token, decode_confirmation_token

from django.views.decorators.http import require_POST


def login_view(request):

    if request.method == "POST":
        form = EmailAuthenticationForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect("pages:dashboard")
    else:
        form = EmailAuthenticationForm()

    return render(request, "accounts/login.html", {"form": form})


def register_view(request):

    if request.method == "POST":
        form = PendingRegistrationForm(request.POST)

        if form.is_valid():
            pending_registration = PendingRegistration(
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
                email=form.cleaned_data["email"],
            )

            pending_registration.set_password(form.cleaned_data["password_1"])
            pending_registration.save()

            token = create_confirmation_token(pending_registration)

            confirmation_path = reverse(
                "accounts:confirm_registration", 
                kwargs={"token": token},)

            confirmation_url = request.build_absolute_uri(confirmation_path)

            send_mail(
                subject="Confirm your registration",
                message=(
                    "Confirm your Property Operations Manager account:\n\n"
                    f"{confirmation_url}"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[pending_registration.email],
            )

            return redirect("accounts:registration_pending")

    else:
        form = PendingRegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


def registration_pending_view(request):
    return render(request, "accounts/registration_pending.html")


@login_required
@require_POST
def logout_view(request):
    logout(request)
    return redirect("accounts:login")


def confirm_registration_view(request, token):
    try:
        token_data = decode_confirmation_token(token)
        pending_registration_id = token_data["pending_registration_id"]
    except (signing.BadSignature, signing.SignatureExpired, KeyError, TypeError):
        return render(
            request, 
            "accounts/confirm_registration.html", 
            {"error": "This confirmation link is invalid or has expired."},
            status=400,
        )

    with transaction.atomic():
        pending_registration = PendingRegistration.objects.select_for_update().filter(pk=pending_registration_id).first()

        if pending_registration is None or pending_registration.is_expired:
            return render(
                request, 
                "accounts/confirm_registration.html",
                {"error": "This confirmation link is invalid or has expired."},
                status=400,
            )

        user = User(
            first_name=pending_registration.first_name,
            last_name=pending_registration.last_name,
            email=pending_registration.email,
        )

        user.password = pending_registration.password_hash
        user.save()

        pending_registration.delete()

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")

    return redirect("pages:dashboard")







