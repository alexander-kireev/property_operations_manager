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
        return User.objects.create_user(
            email=email,
            first_name="Alice",
            last_name="Smith",
            password=self.TEST_PASSWORD
        ) 

    def test_valid_data_creates_task_with_default_values(self):
        user = self.create_user("alice.smith@example.com")
        task = Task.objects.create(user=user, **self.TASK_DATA)

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

        self.assertEqual(task.issue.pk, issue.pk)

    def test_task_can_be_created_with_property_relation(self):
        user = self.create_user("alice.smith@example.com")
        property_record = Property.objects.create(user=user, **self.PROPERTY_DATA)
        data = self.TASK_DATA.copy()
        data["property"] = property_record

        task = Task.objects.create(user=user, **data)

        self.assertEqual(task.property.pk, property_record.pk)

    def test_task_cannot_be_created_with_simultaneous_property_and_issue_relations(self):
        user = self.create_user("alice.smith@example.com")
        property_record = Property.objects.create(user=user, **self.PROPERTY_DATA)
        issue = Issue.objects.create(user=user, **self.ISSUE_DATA)
        data = self.TASK_DATA.copy()
        data["issue"] = issue
        data["property"] = property_record

        with self.assertRaises(IntegrityError) as raised:
            with transaction.atomic():
                Task.objects.create(user=user, **data)

        self.assertEqual(Task.objects.count(), 0)
        self.assertEqual(
            raised.exception.__cause__.diag.constraint_name,
            "task_has_at_most_one_parent",
        )

    def test_str_method_returns_title(self):
        user = self.create_user("alice.smith@example.com")
        task = Task.objects.create(user=user, **self.TASK_DATA)

        title = task.__str__()

        self.assertEqual(title, task.title)

    def test_deleting_related_issue_sets_field_to_null(self):
        user = self.create_user("alice.smith@example.com")
        issue = Issue.objects.create(user=user, **self.ISSUE_DATA)
        data = self.TASK_DATA.copy()
        data["issue"] = issue

        task = Task.objects.create(user=user, **data)

        issue.delete()
        task.refresh_from_db()

        self.assertIsNone(task.issue)

    def test_deleting_related_property_sets_field_to_null(self):
        user = self.create_user("alice.smith@example.com")
        property_record = Property.objects.create(user=user, **self.PROPERTY_DATA)
        data = self.TASK_DATA.copy()
        data["property"] = property_record

        task = Task.objects.create(user=user, **data)

        property_record.delete()
        task.refresh_from_db()

        self.assertIsNone(task.property)
    


class TaskFormTests(TestCase):
    TEST_PASSWORD = "HolidayHome123!"
    TASK_DATA = {
        "title": "call plumber about roof leak",
        "description": "Hill House 4 roof has been leaking since Friday 06.10",
        "priority": Task.Priority.LOW,
    }
    PROPERTY_DATA = {
        "name": "Hill House 4"
    }
    ISSUE_DATA = {
        "title": "Hill House issue"
    }

    def setUp(self):
        self.user = User.objects.create_user(
            email="alice@example.com",
            first_name="Alice",
            last_name="Smith",
            password=self.TEST_PASSWORD,
        )

    def create_user2(self):
        return User.objects.create_user(
            email="bob.jackson@example.com",
            first_name="Bob",
            last_name="Jackson",
            password=self.TEST_PASSWORD
        )

    def create_issue(self, *, data, user):
        return Issue.objects.create(user=user, title=data["title"])

    def create_property(self, *, data, user):
        return Property.objects.create(user=user, name=data["name"])

    def create_task(self, *, data, user):
        form = TaskForm(data=data, user=user)
        task = form.save(commit=False)
        task.user = user
        form.save()
        return Task.objects.get(pk=task.pk)
    
    def test_valid_form_can_create_standalone_task(self):
        task = self.create_task(data=self.TASK_DATA, user=self.user)
        
        self.assertIsNone(task.property)
        self.assertIsNone(task.issue)
    
    def test_duplicate_name_for_tasks_is_allowed(self):
        self.create_task(data=self.TASK_DATA, user=self.user)
        self.create_task(data=self.TASK_DATA, user=self.user)

        self.assertEqual(Task.objects.filter(title=self.TASK_DATA["title"]).count(), 2)

    def test_valid_form_can_create_task_with_issue_relation(self):
        data = self.TASK_DATA.copy()
        issue = self.create_issue(data=self.ISSUE_DATA, user=self.user)
        data["issue"] = issue
        task = self.create_task(data=data, user=self.user)

        self.assertEqual(task.issue.pk, issue.pk)

    def test_valid_form_can_create_task_with_property_relation(self):
        data = self.TASK_DATA.copy()
        property_record = self.create_property(data=self.PROPERTY_DATA, user=self.user)
        data["property"] = property_record
        task = self.create_task(data=data, user=self.user)

        self.assertEqual(task.property.pk, property_record.pk)

    def test_invalid_form_cannot_create_task_with_issue_and_property_simultaneously(self):
        data = self.TASK_DATA.copy()
        property_record = self.create_property(data=self.PROPERTY_DATA, user=self.user)
        issue = self.create_issue(data=self.ISSUE_DATA, user=self.user)
        data["property"] = property_record
        data["issue"] = issue

        form = TaskForm(data=data, user=self.user)

        self.assertFalse(form.is_valid(), form.errors)

    def test_invalid_form_cannot_create_task_with_no_user(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                form = TaskForm(data=self.TASK_DATA, user=None)
                task = form.save(commit=False)
                task.user = None
                form.save()

        self.assertEqual(Task.objects.count(), 0)

    def test_task_can_be_edited_via_form_with_valid_data(self):
        task = self.create_task(data=self.TASK_DATA, user=self.user)
        original_pk = task.pk

        new_data = {
            "title": "amended title",
            "description": "amended description",
            "priority": Task.Priority.HIGH,
        }

        form = TaskForm(data=new_data, user=self.user, instance=task)

        self.assertTrue(form.is_valid())
        updated_task = form.save()
        updated_task.refresh_from_db()

        self.assertEqual(updated_task.pk, original_pk)
        self.assertEqual(updated_task.title, new_data["title"])
        self.assertEqual(updated_task.description, new_data["description"])
        self.assertEqual(updated_task.priority, new_data["priority"])
        self.assertEqual(updated_task.user, self.user)
        self.assertEqual(Task.objects.count(), 1)

    def test_past_scheduled_date_is_rejected(self):
        data = self.TASK_DATA.copy()
        data["scheduled_date"] = timezone.localdate() - timedelta(days=1)

        form = TaskForm(data=data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertFormError(
            form,
            "scheduled_date",
            "A task can only be scheduled for today or later.",
        )

    def test_past_completion_deadline_is_rejected(self):
        data = self.TASK_DATA.copy()
        data["completion_deadline"] = timezone.localdate() - timedelta(days=1)

        form = TaskForm(data=data, user=self.user)

        self.assertFalse(form.is_valid())
        self.assertFormError(
            form,
            "completion_deadline",
            "A task's deadline can only be set for today or later."
        )

    def test_today_or_future_scheduled_date_is_accepted(self):
        data = self.TASK_DATA.copy()
        data["scheduled_date"] = timezone.localdate()

        form = TaskForm(data=data, user=self.user)

        self.assertTrue(form.is_valid())

    def test_today_or_future_completion_deadline_is_accepted(self):
        data = self.TASK_DATA.copy()
        data["completion_deadline"] = timezone.localdate()

        form = TaskForm(data=data, user=self.user)

        self.assertTrue(form.is_valid())

    def test_invalid_form_with_another_users_issue_relation_is_rejected(self):
        user2 = self.create_user2()
        issue2 = self.create_issue(data=self.ISSUE_DATA, user=user2)
        data = self.TASK_DATA.copy()
        data["issue"] = issue2
        form = TaskForm(data=data, user=self.user)

        self.assertFalse(form.is_valid())

    def test_invalid_form_with_another_users_property_relation_is_rejected(self):
        user2 = self.create_user2()
        property2 = self.create_property(data=self.PROPERTY_DATA, user=user2)
        data = self.TASK_DATA.copy()
        data["property"] = property2
        form = TaskForm(data=data, user=self.user)

        self.assertFalse(form.is_valid())
