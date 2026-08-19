from django.test import TestCase
from .models import User, PendingRegistration

from django.urls import reverse

from .forms import PendingRegistrationForm


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
        self.assertEqual(pending_registration.first_name, "Alice")
        self.assertEqual(pending_registration.last_name, "Smith")
        self.assertTrue(pending_registration.check_password(self.VALID_DATA["password_1"]))
        self.assertNotEqual(pending_registration.password_hash, self.VALID_DATA["password_1"])