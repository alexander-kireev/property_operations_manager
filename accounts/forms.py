from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, SetPasswordForm, UserChangeForm, UserCreationForm
from django.contrib.auth.password_validation import validate_password

from .models import User, PendingEmailChange, PendingRegistration
from django.utils import timezone

from django import forms


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email",)


class CustomUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"


class PendingRegistrationForm(forms.Form):
    first_name = forms.CharField(max_length=50)
    last_name = forms.CharField(max_length=50)
    email = forms.EmailField(max_length=254)
    password_1 = forms.CharField(strip=False, widget=forms.PasswordInput)
    password_2 = forms.CharField(strip=False, widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
            field.widget.attrs["autocomplete"] = "off"

    def clean_email(self):
        email = self.cleaned_data["email"].lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account already exists with this email address.")

        if PendingRegistration.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A registration is already pending for this email address.")

        return email

    def clean_password_1(self):
        password_1 = self.cleaned_data["password_1"]

        validate_password(password_1)

        return password_1

    def clean_password_2(self):
        password_1 = self.cleaned_data.get("password_1")
        password_2 = self.cleaned_data["password_2"]

        if password_1 and password_1 != password_2:
            raise forms.ValidationError("The passwords do not match")

        return password_2


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label="Email", max_length=254)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
        self.fields["username"].widget.attrs["autocomplete"] = "username"
        self.fields["password"].widget.attrs["autocomplete"] = "current-password"

    def clean_username(self):
        email = self.cleaned_data["username"]
        return email.lower()


class ProfileForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
            field.widget.attrs["autocomplete"] = "off"

    class Meta:
        model = User
        fields = ("first_name", "last_name")


class EmailChangeForm(forms.Form):
    new_email = forms.EmailField(label="New email", max_length=254)
    current_password = forms.CharField(strip=False, widget=forms.PasswordInput)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
        self.fields["new_email"].widget.attrs["autocomplete"] = "off"
        self.fields["current_password"].widget.attrs["autocomplete"] = "current-password"

    def clean_new_email(self):
        new_email = self.cleaned_data["new_email"].strip().lower()

        if new_email == self.user.email.lower():
            raise forms.ValidationError("This is already your current email address.")

        if (User.objects.filter(email__iexact=new_email).exists() or
            PendingRegistration.objects.filter(email__iexact=new_email).exists()) :
            raise forms.ValidationError("An account already exists with this email address.")

        if PendingEmailChange.objects.filter(new_email__iexact=new_email, expires_at__gt=timezone.now()).exclude(user=self.user).exists():
            raise forms.ValidationError("A change to this email address is already pending.")

        return new_email


class PasswordResetConfirmForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
            field.widget.attrs["autocomplete"] = "off"


class AccountPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
        self.fields["old_password"].widget.attrs["autocomplete"] = "current-password"
        self.fields["new_password1"].widget.attrs["autocomplete"] = "new-password"
        self.fields["new_password2"].widget.attrs["autocomplete"] = "new-password"

