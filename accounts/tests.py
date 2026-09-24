from datetime import datetime, timedelta
from urllib.parse import urlsplit
from unittest.mock import patch

from django.test import TestCase, override_settings
from .models import User, PendingEmailChange, PendingRegistration

from django.urls import reverse
from django.core import mail
from django.utils import timezone
from django.contrib import auth
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .forms import EmailChangeForm, PendingRegistrationForm, ProfileForm

from .tokens import create_confirmation_token


class UserManagerTests(TestCase):
    TEST_PASSWORD = "Mostsecurepassword123!"
    TEST_EMAIL = "TesT_eMaiL@ExamPle.coM"

    def test_create_user_with_email_and_password(self):
        user = User.objects.create_user(email=self.TEST_EMAIL, password=self.TEST_PASSWORD)
        user.refresh_from_db()

        self.assertEqual(user.email, self.TEST_EMAIL.lower())
        self.assertTrue(user.check_password(self.TEST_PASSWORD))
        self.assertNotEqual(user.password, self.TEST_PASSWORD)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_user_without_email(self):
        with self.assertRaisesMessage(ValueError, "An email address is required."):
            User.objects.create_user(email="", password=self.TEST_PASSWORD)

        self.assertEqual(User.objects.count(), 0)

    def test_create_superuser_with_required_privileges(self):
        superuser = User.objects.create_superuser(email=self.TEST_EMAIL, password=self.TEST_PASSWORD)
        superuser.refresh_from_db()

        self.assertEqual(superuser.email, self.TEST_EMAIL.lower())
        self.assertTrue(superuser.check_password(self.TEST_PASSWORD))
        self.assertNotEqual(superuser.password, self.TEST_PASSWORD)
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)

    def test_create_superuser_with_is_staff_false_raises_error(self):
        with self.assertRaisesMessage(ValueError, "A superuser must have is_staff=True."):
            User.objects.create_superuser(email=self.TEST_EMAIL, password=self.TEST_PASSWORD, is_staff=False)

        self.assertEqual(User.objects.count(), 0)

    def test_create_superuser_with_is_superuser_false_raises_error(self):
        with self.assertRaisesMessage(ValueError, "A superuser must have is_superuser=True."):
            User.objects.create_superuser(email=self.TEST_EMAIL, password=self.TEST_PASSWORD, is_superuser=False)

        self.assertEqual(User.objects.count(), 0)


class PendingRegistrationFormTests(TestCase):
    VALID_DATA = {
        "first_name": "  Alice  ",
        "last_name": "  Smith  ",
        "email": "  ALICE.smith@EXAMPLE.com  ",
        "password_1": "HolidayHome123!",
        "password_2": "HolidayHome123!",
    }

    def test_valid_registration_form(self):
        form = PendingRegistrationForm(data=self.VALID_DATA)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["first_name"], "Alice")
        self.assertEqual(form.cleaned_data["last_name"], "Smith")
        self.assertEqual(form.cleaned_data["email"], "alice.smith@example.com")

    def test_name_and_email_limits(self):
        for field, length in (("first_name", 50), ("last_name", 50), ("email", 254)):
            data = self.VALID_DATA.copy()
            data[field] = ("a" * (length - 12) + "@example.com") if field == "email" else "A" * length
            self.assertTrue(PendingRegistrationForm(data=data).is_valid(), field)
            data[field] = ("a" * (length - 11) + "@example.com") if field == "email" else "A" * (length + 1)
            form = PendingRegistrationForm(data=data)
            self.assertFalse(form.is_valid())
            self.assertIn(field, form.errors)

    def test_weak_passwords_are_rejected(self):
        data = self.VALID_DATA.copy()
        data["password_1"] = "Password"
        data["password_2"] = data["password_1"]

        form = PendingRegistrationForm(data=data)

        self.assertFalse(form.is_valid())
        self.assertIn("password_1", form.errors)

    def test_missing_last_name(self):
        data = self.VALID_DATA.copy()
        data["last_name"] = "   "

        form = PendingRegistrationForm(data=data)

        self.assertFalse(form.is_valid())
        self.assertIn("last_name", form.errors)

    def test_invalid_email(self):
        data = self.VALID_DATA.copy()
        data["email"] = "invalid.email.com"

        form = PendingRegistrationForm(data=data)

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)


    def test_passwords_dont_match(self):
        data = self.VALID_DATA.copy()
        data["password_2"] = "DifferentStrongPassword12!"

        form = PendingRegistrationForm(data=data)

        self.assertFalse(form.is_valid())
        self.assertIn("password_2", form.errors)

    def test_duplicate_email_in_pending_registration(self):
        pending_registration = PendingRegistration(
            first_name="Pending",
            last_name="User",
            email="pending@email.com",
        )

        pending_registration.set_password(self.VALID_DATA["password_1"])
        pending_registration.save()

        data = self.VALID_DATA.copy()
        data["email"] = "PENDING@EMAIL.COM"

        form = PendingRegistrationForm(data=data)

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_duplicate_email_in_users(self):
        User.objects.create_user(
            first_name="Existing",
            last_name="User",
            email="existing@email.com",
            password=self.VALID_DATA["password_1"]
        )

        data = self.VALID_DATA.copy()
        data["email"] = "EXISTING@EMAIL.COM"

        form = PendingRegistrationForm(data=data)

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)


class EmailChangeFormLimitTests(TestCase):
    def test_new_email_limit(self):
        user = User.objects.create_user(email="current@example.com", password="HolidayHome123!")
        valid_email = "a" * 242 + "@example.com"
        form = EmailChangeForm(data={"new_email": valid_email, "current_password": "HolidayHome123!"}, user=user)
        self.assertTrue(form.is_valid(), form.errors)

        form = EmailChangeForm(data={"new_email": "a" + valid_email, "current_password": "HolidayHome123!"}, user=user)
        self.assertFalse(form.is_valid())
        self.assertIn("new_email", form.errors)


class RegistrationViewTests(TestCase):
    VALID_DATA = {
        "first_name": "  Alice  ",
        "last_name": "  Smith  ",
        "email": "alice.smith@example.com",
        "password_1": "HolidayHome123!",
        "password_2": "HolidayHome123!",
    }

    VALID_CLEANED_DATA = {
        "first_name": "Alice",
        "last_name": "Smith",
        "email": "alice.smith@example.com",
        "password_1": "HolidayHome123!",
        "password_2": "HolidayHome123!",
    }

    def create_valid_pending_registration(self):
        pending_registration = PendingRegistration(
            first_name=self.VALID_CLEANED_DATA["first_name"],
            last_name=self.VALID_CLEANED_DATA["last_name"],
            email=self.VALID_CLEANED_DATA["email"]
        )

        pending_registration.set_password(self.VALID_CLEANED_DATA["password_1"])

        return pending_registration

    def create_valid_pending_registration_and_token_and_return(self):
        pending_registration = self.create_valid_pending_registration()
        pending_registration.save()

        token = create_confirmation_token(pending_registration)

        confirmation_url = reverse("accounts:confirm_registration", kwargs={"token": token})

        response = self.client.get(confirmation_url)

        return {
            "token": token,
            "pending_registration": pending_registration,
            "confirmation_url": confirmation_url,
            "response": response,
            "pk": pending_registration.pk,
        }

    def test_get_registration_page(self):
        response = self.client.get(reverse("accounts:register"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/register.html")
        self.assertIsInstance(response.context["form"], PendingRegistrationForm)

    def test_invalid_post_does_not_create_pending_registration(self):
        data = self.VALID_DATA.copy()
        data["password_2"] = "DifferentPassword12!"

        post_response = self.client.post(reverse("accounts:register"), data=data)

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("password_2", response.context["form"].errors)
        self.assertIsNone(response.context["form"]["password_1"].value())
        self.assertIsNone(response.context["form"]["password_2"].value())
        self.assertEqual(PendingRegistration.objects.count(), 0)

    def test_valid_post_creates_pending_registration(self):
        response = self.client.post(reverse("accounts:register"), data=self.VALID_DATA)

        self.assertRedirects(response, reverse("accounts:registration_pending"))
        pending_registration = PendingRegistration.objects.get(email=self.VALID_DATA["email"])
        self.assertEqual(pending_registration.first_name, self.VALID_CLEANED_DATA["first_name"])
        self.assertEqual(pending_registration.last_name, self.VALID_CLEANED_DATA["last_name"])
        self.assertTrue(pending_registration.check_password(self.VALID_DATA["password_1"]))
        self.assertNotEqual(pending_registration.password_hash, self.VALID_DATA["password_1"])

    def test_valid_registration_sends_confirmation_email(self):
        self.client.post(
            reverse("accounts:register"),
            data=self.VALID_DATA
        )

        self.assertEqual(len(mail.outbox), 1)

        sent_email = mail.outbox[0]

        self.assertEqual(sent_email.to, [self.VALID_DATA["email"]])

        self.assertEqual(sent_email.subject, "Confirm your registration")

        self.assertIn("http://testserver/accounts/confirm/", sent_email.body,)

    def test_pending_registration_deleted_after_user_created_and_user_is_created(self):
        r = self.create_valid_pending_registration_and_token_and_return()

        self.assertTrue(User.objects.filter(email=self.VALID_CLEANED_DATA["email"]).exists())
        self.assertFalse(PendingRegistration.objects.filter(pk=r["pk"]).exists())
    
    def test_invalid_token_returns_400_and_does_not_create_user_and_does_not_delete_pending_request(self):
        pending_registration = self.create_valid_pending_registration()
        pending_registration.save()

        token = create_confirmation_token(pending_registration)
        token = token + "invalid_token"

        confirmation_url = reverse("accounts:confirm_registration", kwargs={"token": token})

        response = self.client.get(confirmation_url)

        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "accounts/confirm_registration.html")

        pending_registration_id = pending_registration.pk

        self.assertTrue(PendingRegistration.objects.filter(pk=pending_registration_id).exists())
        self.assertFalse(User.objects.filter(email=pending_registration.email).exists())

    def test_expired_registration_returns_400_and_does_not_create_user_and_does_not_delete_pending_request(self):
        pending_registration = self.create_valid_pending_registration()

        pending_registration.expires_at = (
            timezone.now() - timedelta(seconds=1)
        )

        pending_registration.save()

        token = create_confirmation_token(pending_registration)

        confirmation_url = reverse("accounts:confirm_registration", kwargs={"token": token})

        response = self.client.get(confirmation_url)

        self.assertEqual(response.status_code, 400)

        self.assertEqual(User.objects.count(), 0)
        self.assertTrue(PendingRegistration.objects.filter(pk=pending_registration.pk).exists())

    def test_reused_token_returns_is_rejected_and_does_not_create_duplicate_user(self):
        r = self.create_valid_pending_registration_and_token_and_return()

        self.assertTrue(User.objects.filter(email=self.VALID_CLEANED_DATA["email"]).exists())
        self.assertFalse(PendingRegistration.objects.filter(pk=r["pk"]).exists())

        response_2 = self.client.get(r["confirmation_url"])

        self.assertEqual(response_2.status_code, 400)
        self.assertTemplateUsed(response_2, "accounts/confirm_registration.html")

        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(PendingRegistration.objects.count(), 0)

    def test_valid_token_creates_and_authenticates_user(self):
        r = self.create_valid_pending_registration_and_token_and_return()

        self.assertTrue(User.objects.filter(email=self.VALID_CLEANED_DATA["email"]).exists())
        user = User.objects.get(email=self.VALID_CLEANED_DATA["email"])

        self.assertRedirects(r["response"], reverse("pages:dashboard"))

        dashboard_response = self.client.get(reverse("pages:dashboard"))

        self.assertEqual(dashboard_response.status_code, 200)

    def test_password_works_after_hash_transfer(self):
        r = self.create_valid_pending_registration_and_token_and_return()

        user = User.objects.get(email=r["pending_registration"].email)

        self.assertTrue(user.check_password(self.VALID_DATA["password_1"]))

        
class UserAuthenticationTests(TestCase):
    VALID_CLEANED_DATA = {
        "first_name": "Alice",
        "last_name": "Smith",
        "email": "alice.smith@example.com",
        "password_1": "HolidayHome123!",
        "password_2": "HolidayHome123!",
    }

    def setUp(self):
        User.objects.create_user(
            email=self.VALID_CLEANED_DATA["email"],
            first_name=self.VALID_CLEANED_DATA["first_name"],
            last_name=self.VALID_CLEANED_DATA["last_name"],
            password=self.VALID_CLEANED_DATA["password_1"]
        )    

    def test_valid_details_log_user_in(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": self.VALID_CLEANED_DATA["email"],
                "password": self.VALID_CLEANED_DATA["password_1"]
            }
        )

        self.assertRedirects(response, reverse("pages:dashboard"))
        user = auth.get_user(self.client)
        self.assertTrue(user.is_authenticated)


    def test_invalid_details_do_not_log_user_in(self):
        invalid_password = f"{self.VALID_CLEANED_DATA['password_1']}_invalid"

        post_response = self.client.post(
            reverse("accounts:login"),
            {
                "username": self.VALID_CLEANED_DATA["email"],
                "password": invalid_password
            }
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        user = auth.get_user(self.client)
        self.assertFalse(user.is_authenticated)

        form = response.context["form"]
        self.assertTrue(form.non_field_errors())
        self.assertIsNone(form["password"].value())


    def test_post_request_logs_user_out(self):
        self.client.login(
            email=self.VALID_CLEANED_DATA["email"],
            password=self.VALID_CLEANED_DATA["password_1"]
        )

        user = auth.get_user(self.client)
        self.assertTrue(user.is_authenticated)

        response = self.client.post(
            reverse("accounts:logout")
        )

        self.assertEqual(response.status_code, 302)
        user = auth.get_user(self.client)
        self.assertFalse(user.is_authenticated)

        

    def test_get_request_does_not_log_user_out(self):
        self.client.login(
            email=self.VALID_CLEANED_DATA["email"],
            password=self.VALID_CLEANED_DATA["password_1"]
        )

        user = auth.get_user(self.client)
        self.assertTrue(user.is_authenticated)

        response = self.client.get(
            reverse("accounts:logout")
        )

        self.assertEqual(response.status_code, 405)
        user = auth.get_user(self.client)
        self.assertTrue(user.is_authenticated)


class UserAccountManagementTests(TestCase):
    USER_1 = {
        "first_name": "Alice",
        "last_name": "Smith",
        "email": "alice.smith@example.com",
        "password": "HolidayHome123!",
    }

    USER_2 = {
        "first_name": "Bob",
        "last_name": "Jackson",
        "email": "bob.jackson@example.com",
        "password": "CountryRoad123!",
    }

    NEW_PASSWORD = "NewHolidayHome456!"

    def create_user(self, user_data):
        return User.objects.create_user(
            email=user_data["email"],
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            password=user_data["password"]
        )

    def login_user(self, user_data):
        self.client.login(
            username=user_data["email"],
            password=user_data["password"]
        )

    def create_password_reset_url(self, user, token=None):
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = token or default_token_generator.make_token(user)

        return reverse(
            "accounts:password_reset_confirm",
            kwargs={"uidb64": uidb64, "token": token},
        )

    def open_password_reset_form(self, user, token=None):
        response = self.client.get(self.create_password_reset_url(user, token))
        self.assertEqual(response.status_code, 302)

        return response.url

    def test_account_change_forms_load_empty_with_fresh_field_guard(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)

        for route, fields in (
            ("accounts:change_email", ("new_email", "current_password")),
            ("accounts:change_password", ("old_password", "new_password1", "new_password2")),
        ):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertContains(response, 'data-fresh-account-form')
                self.assertContains(response, 'js/fresh-account-form.js')
                for name in fields:
                    self.assertIsNone(response.context["form"][name].value())

    def test_profile_page_loads_for_authenticated_user(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:profile_page"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/profile_page.html")

        form = response.context["profile_form"]
        self.assertIsInstance(form, ProfileForm)
        self.assertEqual(form.instance, user)

    def test_profile_page_does_not_load_for_unauthenticated_user(self):
        response = self.client.get(reverse("accounts:profile_page"))
        self.assertEqual(response.status_code, 302)

    def test_user_can_only_access_own_profile_page(self):
        user_2 = self.create_user(self.USER_2)
        user = self.create_user(self.USER_1)

        self.client.force_login(user)

        response = self.client.get(reverse("accounts:profile_page"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/profile_page.html")

        form = response.context["profile_form"]
        self.assertIsInstance(form, ProfileForm)
        self.assertNotEqual(form.instance, user_2)
        self.assertEqual(form.instance, user)

    def test_email_change_valid_form_and_valid_password_is_successful(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)

        new_email = "alice.new@example.com"

        response = self.client.post(
            reverse("accounts:change_email"),
            {
                "new_email": new_email,
                "current_password": self.USER_1["password"],
            },
        )

        self.assertRedirects(response, reverse("accounts:change_email"))

        user.refresh_from_db()
        self.assertEqual(user.email, self.USER_1["email"])
        self.assertEqual(PendingEmailChange.objects.get(user=user).new_email, new_email)
        self.assertEqual(mail.outbox[-1].to, [new_email])

        confirmation_url = next(line for line in mail.outbox[-1].body.splitlines() if "/change_email/confirm/" in line)
        confirmation_path = urlsplit(confirmation_url).path
        self.assertEqual(self.client.get(confirmation_path).status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.email, self.USER_1["email"])

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(confirmation_path)
        self.assertRedirects(response, reverse("accounts:email_change_complete"))
        user.refresh_from_db()
        self.assertEqual(user.email, new_email)
        self.assertFalse(PendingEmailChange.objects.filter(user=user).exists())
        self.assertEqual(mail.outbox[-1].to, [self.USER_1["email"]])
        self.assertEqual(self.client.post(confirmation_path).status_code, 400)

    def test_email_change_link_expires_and_replaced_link_cannot_be_used(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)
        self.client.post(reverse("accounts:change_email"), {"new_email": "first@example.com", "current_password": self.USER_1["password"]})
        first_path = urlsplit(next(line for line in mail.outbox[-1].body.splitlines() if "/change_email/confirm/" in line)).path
        self.client.post(reverse("accounts:change_email"), {"new_email": "second@example.com", "current_password": self.USER_1["password"]})
        self.assertEqual(self.client.post(first_path).status_code, 400)
        pending = PendingEmailChange.objects.get(user=user)
        pending.expires_at = timezone.now() - timedelta(seconds=1)
        pending.save(update_fields=["expires_at"])
        second_path = urlsplit(next(line for line in mail.outbox[-1].body.splitlines() if "/change_email/confirm/" in line)).path
        self.assertEqual(self.client.post(second_path).status_code, 400)
        user.refresh_from_db()
        self.assertEqual(user.email, self.USER_1["email"])

    def test_email_change_rejects_address_taken_after_request(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)
        target = "later@example.com"
        self.client.post(reverse("accounts:change_email"), {"new_email": target, "current_password": self.USER_1["password"]})
        confirmation_path = urlsplit(next(line for line in mail.outbox[-1].body.splitlines() if "/change_email/confirm/" in line)).path
        User.objects.create_user(email=target, password="StrongPassword123!")
        self.assertEqual(self.client.post(confirmation_path).status_code, 409)
        user.refresh_from_db()
        self.assertEqual(user.email, self.USER_1["email"])

    def test_old_login_works_until_new_email_is_verified(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)
        target = "alice.verified@example.com"
        self.client.post(reverse("accounts:change_email"), {"new_email": target, "current_password": self.USER_1["password"]})
        confirmation_path = urlsplit(next(line for line in mail.outbox[-1].body.splitlines() if "/change_email/confirm/" in line)).path

        self.client.logout()
        self.assertTrue(self.client.login(username=self.USER_1["email"], password=self.USER_1["password"]))
        self.client.logout()
        self.assertFalse(self.client.login(username=target, password=self.USER_1["password"]))
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(confirmation_path)
        self.assertFalse(self.client.login(username=self.USER_1["email"], password=self.USER_1["password"]))
        self.assertTrue(self.client.login(username=target, password=self.USER_1["password"]))

    def test_email_change_taken_email_is_rejected(self):
        user = self.create_user(self.USER_1)
        user_2 = self.create_user(self.USER_2)
        self.client.force_login(user)

        post_response = self.client.post(
            reverse("accounts:change_email"),
            {
                "new_email": user_2.email,
                "current_password": self.USER_1["password"],
            },
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(response.context["form"]["new_email"].value(), user_2.email)
        self.assertIsNone(response.context["form"]["current_password"].value())
        self.assertContains(response, "data-preserve-restored-email")

        user.refresh_from_db()
        self.assertEqual(user.email, self.USER_1["email"])

    def test_email_change_valid_email_invalid_password_is_rejected(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)

        new_email = "alice.new@example.com"

        post_response = self.client.post(
            reverse("accounts:change_email"),
            {
                "new_email": new_email,
                "current_password": f"{self.USER_1['password']}_invalid",
            },
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(response.context["form"]["new_email"].value(), new_email)
        self.assertIsNone(response.context["form"]["current_password"].value())
        self.assertContains(response, "data-preserve-restored-email")

        user.refresh_from_db()
        self.assertEqual(user.email, self.USER_1["email"])

    def test_email_change_does_not_require_typed_email_confirmation(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)

        post_response = self.client.post(
            reverse("accounts:change_email"),
            {
                "new_email": "alice.new@example.com",
                "current_password": self.USER_1["password"],
            },
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertEqual(post_response.url, reverse("accounts:change_email"))

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].errors)
        self.assertContains(response, "Verification is pending")

        user.refresh_from_db()
        self.assertEqual(user.email, self.USER_1["email"])

    def test_first_name_change_valid_first_name_is_successful(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)

        new_first_name = "Alicia"

        response = self.client.post(
            reverse("accounts:profile_page"),
            {
                "first_name": new_first_name,
                "last_name": self.USER_1["last_name"],
            },
        )

        self.assertRedirects(response, reverse("accounts:profile_page"))

        user.refresh_from_db()
        self.assertEqual(user.first_name, new_first_name)
        self.assertEqual(user.last_name, self.USER_1["last_name"])

    def test_first_name_change_invalid_first_name_is_rejected(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)

        post_response = self.client.post(
            reverse("accounts:profile_page"),
            {
                "first_name": "",
                "last_name": self.USER_1["last_name"],
            },
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["profile_form"].errors)

        user.refresh_from_db()
        self.assertEqual(user.first_name, self.USER_1["first_name"])
        self.assertEqual(user.last_name, self.USER_1["last_name"])

    def test_last_name_change_valid_last_name_is_successful(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)

        new_last_name = "Jones"

        response = self.client.post(
            reverse("accounts:profile_page"),
            {
                "first_name": self.USER_1["first_name"],
                "last_name": new_last_name,
            },
        )

        self.assertRedirects(response, reverse("accounts:profile_page"))

        user.refresh_from_db()
        self.assertEqual(user.first_name, self.USER_1["first_name"])
        self.assertEqual(user.last_name, new_last_name)

    def test_last_name_change_invalid_last_name_is_rejected(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)

        post_response = self.client.post(
            reverse("accounts:profile_page"),
            {
                "first_name": self.USER_1["first_name"],
                "last_name": "",
            },
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["profile_form"].errors)

        user.refresh_from_db()
        self.assertEqual(user.first_name, self.USER_1["first_name"])
        self.assertEqual(user.last_name, self.USER_1["last_name"])

    def test_protected_password_reset_request_sends_token_to_email(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)

        response = self.client.post(reverse("accounts:reset_password_protected"))

        self.assertRedirects(response, reverse("accounts:profile_page"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [user.email])
        self.assertIn("/accounts/password/reset/", mail.outbox[0].body)

    def test_password_reset_with_valid_token_is_successful(self):
        user = self.create_user(self.USER_1)
        password_reset_form_url = self.open_password_reset_form(user)

        response = self.client.post(
            password_reset_form_url,
            {
                "new_password1": self.NEW_PASSWORD,
                "new_password2": self.NEW_PASSWORD,
            },
        )

        self.assertRedirects(response, reverse("accounts:password_reset_complete"))

        user.refresh_from_db()
        self.assertTrue(user.check_password(self.NEW_PASSWORD))
        self.assertFalse(user.check_password(self.USER_1["password"]))

    @override_settings(PASSWORD_RESET_TIMEOUT=3600)
    def test_password_reset_with_expired_token_is_rejected(self):
        user = self.create_user(self.USER_1)

        two_hours_ago = datetime.now() - timedelta(hours=2)

        with patch.object(default_token_generator, "_now", return_value=two_hours_ago):
            token = default_token_generator.make_token(user)

        response = self.client.get(self.create_password_reset_url(user, token))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["validlink"])

        user.refresh_from_db()
        self.assertTrue(user.check_password(self.USER_1["password"]))

    def test_password_reset_with_used_token_is_rejected(self):
        user = self.create_user(self.USER_1)
        token = default_token_generator.make_token(user)
        password_reset_form_url = self.open_password_reset_form(user, token)

        response = self.client.post(
            password_reset_form_url,
            {
                "new_password1": self.NEW_PASSWORD,
                "new_password2": self.NEW_PASSWORD,
            },
        )

        self.assertRedirects(response, reverse("accounts:password_reset_complete"))

        reused_token_response = self.client.get(
            self.create_password_reset_url(user, token)
        )

        self.assertEqual(reused_token_response.status_code, 200)
        self.assertFalse(reused_token_response.context["validlink"])

    def test_password_reset_with_invalid_new_password_is_rejected(self):
        user = self.create_user(self.USER_1)
        password_reset_form_url = self.open_password_reset_form(user)

        post_response = self.client.post(
            password_reset_form_url,
            {
                "new_password1": "password",
                "new_password2": "password",
            },
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertIsNone(response.context["form"]["new_password1"].value())
        self.assertIsNone(response.context["form"]["new_password2"].value())

        user.refresh_from_db()
        self.assertTrue(user.check_password(self.USER_1["password"]))
        self.assertFalse(user.check_password("password"))

    def test_protected_password_change_with_invalid_new_password_is_rejected(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)

        post_response = self.client.post(
            reverse("accounts:change_password"),
            {
                "old_password": self.USER_1["password"],
                "new_password1": "password",
                "new_password2": "password",
            },
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertIsNone(response.context["form"]["old_password"].value())
        self.assertIsNone(response.context["form"]["new_password1"].value())

        user.refresh_from_db()
        self.assertTrue(user.check_password(self.USER_1["password"]))
        self.assertFalse(user.check_password("password"))

    def test_protected_password_change_with_valid_new_password_is_successful(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)

        response = self.client.post(
            reverse("accounts:change_password"),
            {
                "old_password": self.USER_1["password"],
                "new_password1": self.NEW_PASSWORD,
                "new_password2": self.NEW_PASSWORD,
            },
        )

        self.assertRedirects(response, reverse("accounts:change_password"))

        user.refresh_from_db()
        self.assertTrue(user.check_password(self.NEW_PASSWORD))
        self.assertFalse(user.check_password(self.USER_1["password"]))
        self.assertTrue(auth.get_user(self.client).is_authenticated)

    def test_protected_password_change_with_incorrect_current_password_is_rejected(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)

        post_response = self.client.post(
            reverse("accounts:change_password"),
            {
                "old_password": f"{self.USER_1['password']}_invalid",
                "new_password1": self.NEW_PASSWORD,
                "new_password2": self.NEW_PASSWORD,
            },
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertIsNone(response.context["form"]["old_password"].value())
        self.assertIsNone(response.context["form"]["new_password1"].value())

        user.refresh_from_db()
        self.assertTrue(user.check_password(self.USER_1["password"]))
        self.assertFalse(user.check_password(self.NEW_PASSWORD))
