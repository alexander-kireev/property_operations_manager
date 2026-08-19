from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required

from .forms import PendingRegistrationForm

from .models import PendingRegistration


def login_view(request):
    if request.method == "POST":
        pass

    return render(request, "accounts/login.html")

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

            return redirect("accounts:registration_pending")

    else:
        form = PendingRegistrationForm()

    return render(request, "accounts/register.html", {"form": form})

def registration_pending_view(request):
    return render(request, "accounts/registration_pending.html")

@login_required
def logout_view(request):
    logout(request)
    return redirect("accounts:login")