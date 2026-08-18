from django.contrib.auth import get_user_model
from django.test import TestCase
from .models import User


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
        self.assertNotEqual(superuser.password, self.TEST_PASSWORD),
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