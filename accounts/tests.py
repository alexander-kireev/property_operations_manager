from datetime import timedelta

from django.test import TestCase
from .models import User, PendingRegistration

from django.urls import reverse
from django.core import mail
from django.utils import timezone

from .forms import PendingRegistrationForm

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

        response = self.client.post(reverse("accounts:register"), data=data)

        self.assertEqual(response.status_code, 200)
        self.assertIn("password_2", response.context["form"].errors)
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

        




