from django.test import TestCase

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from datetime import timedelta

from accounts.models import User

from .forms import TaskForm
from .models import Task
from property.models import Property
from issue.models import Issue


class TaskModelTests(TestCase):
    TEST_PASSWORD = "HolidayHome123!"
    TASK_DATA = {
        "title": "call plumber about roof leak",
        "description": "Hill House 4 roof has been leaking since Friday 06.10",
    }
    ISSUE_DATA = {
        "title": "test issue",
    }
    PROPERTY_DATA = {
        "name": "test property"
    }

    def create_user(self, email):
        return User.objects.create(
            email=email,
            first_name="Alice",
            last_name="Smith",
            password=self.TEST_PASSWORD
        ) 

    def test_valid_data_creates_task_with_default_values(self):
        user = self.create_user("alice.smith@example.com")
        task = Task.objects.create(user=user, **self.TASK_DATA)

        task.refresh_from_db()

        self.assertEqual(task.user.pk, user.pk)
        self.assertEqual(task.property, None)
        self.assertEqual(task.issue, None)
        self.assertEqual(task.state, Task.State.ACTIVE)
        self.assertEqual(task.priority, Task.Priority.LOW)
        self.assertEqual(task.title, self.TASK_DATA["title"])
        self.assertEqual(task.description, self.TASK_DATA["description"])
        self.assertEqual(task.scheduled_date, None)
        self.assertEqual(task.completion_deadline, None)
        self.assertTrue(task.created_at < timezone.now())
        self.assertEqual(task.terminated_at, None)
        self.assertEqual(task.deleted_at, None)

    def test_task_model_requires_user(self):

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Task.objects.create(**self.TASK_DATA)
            
        self.assertEqual(Task.objects.count(), 0)

    def test_task_can_be_created_with_issue_relation(self):
        user = self.create_user("alice.smith@example.com")
        issue = Issue.objects.create(user=user, **self.ISSUE_DATA)
        data = self.TASK_DATA.copy()
        data["issue"] = issue

        task = Task.objects.create(user=user, **data)
        task.refresh_from_db()
        self.assertEqual(Task.objects.count(), 1)

        self.assertEqual(task)

class TaskFormTests(TestCase):
    TEST_PASSWORD = "HolidayHome123!"
    TASK_DATA = {
        "title": "call plumber about roof leak",
        "description": "Hill House 4 roof has been leaking since Friday 06.10",
        "priority": Task.Priority.LOW,
    }

    def setUp(self):
        self.user = User.objects.create_user(
            email="alice@example.com",
            first_name="Alice",
            last_name="Smith",
            password=self.TEST_PASSWORD,
        )

    def test_duplicate_name_for_tasks_is_allowed(self):
        Task.objects.create(user=self.user, **self.TASK_DATA)

        form = TaskForm(data=self.TASK_DATA, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

        task = form.save(commit=False)
        task.user = self.user

        form.save()

        self.assertEqual(Task.objects.filter(title=self.TASK_DATA["title"]).count(), 2)



