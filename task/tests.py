from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from datetime import timedelta
from unittest.mock import patch

from accounts.models import User

from .forms import TaskForm
from .models import Task
from property.models import Property
from issue.models import Issue
from .selectors import tasks_for_user, filtered_tasks_for_user
from .services import (
    create_task,
    delete_task,
    dismiss_task,
    reactivate_task,
    update_task,
    complete_task,
)

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
        self.assertTrue(form.is_valid(), form.errors)

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
        self.assertIn(
            "A task cannot be related to both a property and an issue simultaneously.",
            form.non_field_errors(),
        )

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

    def test_today_scheduled_date_is_accepted(self):
        data = self.TASK_DATA.copy()
        data["scheduled_date"] = timezone.localdate()

        form = TaskForm(data=data, user=self.user)

        self.assertTrue(form.is_valid())

    def test_future_scheduled_date_is_accepted(self):
        data = self.TASK_DATA.copy()
        data["scheduled_date"] = timezone.localdate() + timedelta(days=1)

        form = TaskForm(data=data, user=self.user)

        self.assertTrue(form.is_valid())

    def test_today_completion_deadline_is_accepted(self):
        data = self.TASK_DATA.copy()
        data["completion_deadline"] = timezone.localdate()

        form = TaskForm(data=data, user=self.user)

        self.assertTrue(form.is_valid())

    def test_future_completion_deadline_is_accepted(self):
        data = self.TASK_DATA.copy()
        data["completion_deadline"] = timezone.localdate() + timedelta(days=1)

        form = TaskForm(data=data, user=self.user)

        self.assertTrue(form.is_valid())

    def test_invalid_form_with_another_users_issue_relation_is_rejected(self):
        user2 = self.create_user2()
        issue2 = self.create_issue(data=self.ISSUE_DATA, user=user2)
        data = self.TASK_DATA.copy()
        data["issue"] = issue2
        form = TaskForm(data=data, user=self.user)

        self.assertFalse(form.is_valid())
        self.assertIn("issue", form.errors)

    def test_invalid_form_with_another_users_property_relation_is_rejected(self):
        user2 = self.create_user2()
        property2 = self.create_property(data=self.PROPERTY_DATA, user=user2)
        data = self.TASK_DATA.copy()
        data["property"] = property2
        form = TaskForm(data=data, user=self.user)

        self.assertFalse(form.is_valid())
        self.assertIn("property", form.errors)

    def test_property_choices_only_include_users_active_non_deleted_properties(self):
        active_property = Property.objects.create(user=self.user, name="Active property")

        Property.objects.create(user=self.user, name="Deactivated property", state=Property.State.DEACTIVATED)
        Property.objects.create(user=self.user, name="Deleted property", deleted_at=timezone.now())

        user2 = self.create_user2()

        Property.objects.create(user=user2, name="Another user's active property")

        form = TaskForm(user=self.user)

        available_properties = list(form.fields["property"].queryset)

        self.assertEqual([active_property], available_properties)

    def test_issue_choices_only_include_users_active_non_deleted_properties(self):
        active_issue = Issue.objects.create(user=self.user, title="Active issue")

        Issue.objects.create(user=self.user, title="Dismissed issue", state=Issue.State.DISMISSED)
        Issue.objects.create(user=self.user, title="Resolved issue", state=Issue.State.RESOLVED)
        Issue.objects.create(user=self.user, title="Deleted issue", deleted_at=timezone.now())

        user2 = self.create_user2()

        Issue.objects.create(user=user2, title="Another user's active issue")

        form = TaskForm(user=self.user)

        available_issues = list(form.fields["issue"].queryset)

        self.assertEqual([active_issue], available_issues)


class TaskSelectorTests(TestCase):
    TEST_PASSWORD = "HolidayHome123!"
    TASK_DATA = [
        {
            "title": "abc active task",
            "description": "abc active task description",
            "state": Task.State.ACTIVE,
            "priority": Task.Priority.MEDIUM,
            "deleted_at": None,
        },
        {
            "title": "xyz active task",
            "description": "xyz active task description",
            "state": Task.State.ACTIVE,
            "priority": Task.Priority.MEDIUM,
            "deleted_at": None,
        },
        {
            "title": "abc completed task",
            "description": "abc completed task description",
            "state": Task.State.COMPLETED,
            "priority": Task.Priority.URGENT,
            "deleted_at": None,
        },
        {
            "title": "xyz completed task",
            "description": "xyz completed task description",
            "state": Task.State.COMPLETED,
            "priority": Task.Priority.MEDIUM,
            "deleted_at": None,
        },
        {
            "title": "abc dismissed task",
            "description": "abc dismissed task description",
            "state": Task.State.DISMISSED,
            "priority": Task.Priority.MEDIUM,
            "deleted_at": None,
        },
        {
            "title": "xyz dismissed task",
            "description": "xyz dismissed task description",
            "state": Task.State.DISMISSED,
            "priority": Task.Priority.MEDIUM,
            "deleted_at": None,
        },
    ]
    DELETED_TASK_DATA = {
        "title": "deleted task",
        "description": "deleted task description",
        "deleted_at": timezone.now(),
    }
    OTHER_USER_TASK_DATA = [
        {
            "title": "other active task",
            "description": "abc active task description",
            "state": Task.State.ACTIVE,
            "priority": Task.Priority.MEDIUM,
            "deleted_at": None,
        },
        {
            "title": "other completed task",
            "description": "abc completed task description",
            "state": Task.State.COMPLETED,
            "priority": Task.Priority.MEDIUM,
            "deleted_at": None,
        },
        {
            "title": "other dismissed task",
            "description": "abc dismissed task description",
            "state": Task.State.DISMISSED,
            "priority": Task.Priority.MEDIUM,
            "deleted_at": None,
        },
        {
            "title": "other deleted task",
            "description": "deleted task description",
            "state": Task.State.ACTIVE,
            "priority": Task.Priority.MEDIUM,
            "deleted_at": timezone.now(),
        },
    ]
    PROPERTY_DATA = {
        "name": "Hill House 4",
        "address": "Hill House address",
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

        for task_data in self.TASK_DATA:
            Task.objects.create(
                user=self.user,
                **task_data,
            )

        Task.objects.create(
            user=self.user,
            **self.DELETED_TASK_DATA,
        )

    def create_tasks_user2(self, user):
        for task_data in self.OTHER_USER_TASK_DATA:
            Task.objects.create(
                user=user,
                **task_data,
            )

    def create_user2(self):
        return User.objects.create_user(
            email="bob.jackson@example.com",
            first_name="Bob",
            last_name="Jackson",
            password=self.TEST_PASSWORD
        )

    def create_issue(self, *, data, user):
        return Issue.objects.create(user=user, **data)

    def create_property(self, *, data, user):
        return Property.objects.create(user=user, **data)

    def create_task(self, *, data, user):
        form = TaskForm(data=data, user=user)
        self.assertTrue(form.is_valid(), form.errors)

        task = form.save(commit=False)
        task.user = user
        form.save()

        return Task.objects.get(pk=task.pk)

    def test_tasks_for_user_are_scopes_to_user_only(self):
        user2 = self.create_user2()
        self.create_tasks_user2(user=user2)

        tasks1 = tasks_for_user(user=self.user)
        tasks2 = tasks_for_user(user=user2)

        self.assertEqual(tasks1.count(), len(self.TASK_DATA))

        for t1 in tasks1:
            for t2 in tasks2:
                self.assertNotEqual(t1.title, t2.title)

    def test_tasks_for_user_filters_out_deleted_tasks(self):
        tasks = tasks_for_user(user=self.user)

        self.assertEqual(tasks.count(), len(self.TASK_DATA))

        deleted_task = Task.objects.get(title=self.DELETED_TASK_DATA["title"])

        for task in tasks:
            self.assertNotEqual(task.title, deleted_task.title)

    def test_filtered_tasks_for_user_scopes_on_search_by_title(self):
        tasks = list(filtered_tasks_for_user(user=self.user, search=self.TASK_DATA[1]["title"]))

        self.assertEqual(len(tasks), 1)

        self.assertEqual(tasks[0].title, self.TASK_DATA[1]["title"])


    def test_filtered_tasks_for_user_scopes_on_search_by_description(self):
        tasks = list(filtered_tasks_for_user(user=self.user, search=self.TASK_DATA[1]["description"]))

        self.assertEqual(len(tasks), 1)

        self.assertEqual(tasks[0].description, self.TASK_DATA[1]["description"])

    def test_filtered_tasks_for_user_scopes_on_search_by_issue(self):
        issue = self.create_issue(data=self.ISSUE_DATA, user=self.user)
        data = self.TASK_DATA[1].copy()
        data["issue"] = issue
        related_task = self.create_task(data=data, user=self.user)

        tasks = list(filtered_tasks_for_user(user=self.user, search=issue.title))

        self.assertEqual([related_task], tasks)

    def test_filtered_tasks_for_user_scopes_on_search_by_property_name(self):
        property_record = self.create_property(data=self.PROPERTY_DATA, user=self.user)
        data = self.TASK_DATA[1].copy()
        data["property"] = property_record
        related_task = self.create_task(data=data, user=self.user)

        tasks = list(filtered_tasks_for_user(user=self.user, search=property_record.name))

        self.assertEqual([related_task], tasks)

    def test_filtered_tasks_for_user_scopes_on_search_by_property_address(self):
        property_record = self.create_property(data=self.PROPERTY_DATA, user=self.user)
        data = self.TASK_DATA[1].copy()
        data["property"] = property_record
        related_task = self.create_task(data=data, user=self.user)

        tasks = list(filtered_tasks_for_user(user=self.user, search=property_record.address))

        self.assertEqual([related_task], tasks)

    def test_filtered_tasks_for_user_filters_by_state(self):
        tasks = list(
            filtered_tasks_for_user(
                user=self.user,
                state=Task.State.COMPLETED,
            )
        )

        self.assertEqual(
            [task.title for task in tasks],
            [
                self.TASK_DATA[2]["title"],
                self.TASK_DATA[3]["title"],
            ],
        )

    def test_filtered_tasks_for_user_filters_by_priority(self):
        tasks = list(
            filtered_tasks_for_user(
                user=self.user,
                priority=Task.Priority.URGENT,
            )
        )

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].title, self.TASK_DATA[2]["title"])

    def test_filtered_tasks_for_user_filters_by_scheduled_period(self):
        today = timezone.localdate()

        today_task = Task.objects.create(
            user=self.user,
            title="schedule fixture today",
            scheduled_date=today,
        )
        next_week_task = Task.objects.create(
            user=self.user,
            title="schedule fixture next week",
            scheduled_date=today + timedelta(days=3),
        )
        later_task = Task.objects.create(
            user=self.user,
            title="schedule fixture later",
            scheduled_date=today + timedelta(days=10),
        )
        past_task = Task.objects.create(
            user=self.user,
            title="schedule fixture past",
            scheduled_date=today - timedelta(days=1),
        )
        unscheduled_task = Task.objects.create(
            user=self.user,
            title="schedule fixture unscheduled",
        )

        expected_tasks = {
            "today": [today_task],
            "next_7_days": [today_task, next_week_task],
            "upcoming": [today_task, next_week_task, later_task],
            "past": [past_task],
            "unscheduled": [unscheduled_task],
        }

        for scheduled_period, expected in expected_tasks.items():
            with self.subTest(scheduled_period=scheduled_period):
                tasks = list(
                    filtered_tasks_for_user(
                        user=self.user,
                        search="schedule fixture",
                        scheduled_period=scheduled_period,
                    )
                )

                self.assertCountEqual(tasks, expected)

    def test_filtered_tasks_for_user_filters_by_deadline_period(self):
        today = timezone.localdate()

        overdue_task = Task.objects.create(
            user=self.user,
            title="deadline fixture overdue",
            completion_deadline=today - timedelta(days=1),
        )
        Task.objects.create(
            user=self.user,
            title="deadline fixture completed overdue",
            state=Task.State.COMPLETED,
            completion_deadline=today - timedelta(days=1),
        )
        today_task = Task.objects.create(
            user=self.user,
            title="deadline fixture today",
            completion_deadline=today,
        )
        next_week_task = Task.objects.create(
            user=self.user,
            title="deadline fixture next week",
            completion_deadline=today + timedelta(days=3),
        )
        later_task = Task.objects.create(
            user=self.user,
            title="deadline fixture later",
            completion_deadline=today + timedelta(days=10),
        )
        no_deadline_task = Task.objects.create(
            user=self.user,
            title="deadline fixture none",
        )

        expected_tasks = {
            "overdue": [overdue_task],
            "today": [today_task],
            "next_7_days": [today_task, next_week_task],
            "upcoming": [today_task, next_week_task, later_task],
            "no_deadline": [no_deadline_task],
        }

        for deadline_period, expected in expected_tasks.items():
            with self.subTest(deadline_period=deadline_period):
                tasks = list(
                    filtered_tasks_for_user(
                        user=self.user,
                        search="deadline fixture",
                        deadline_period=deadline_period,
                    )
                )

                self.assertCountEqual(tasks, expected)

    def test_all_supported_sort_options_return_expected_order(self):
        today = timezone.localdate()

        alpha = Task.objects.create(
            user=self.user,
            title="sort fixture alpha",
            priority=Task.Priority.LOW,
            scheduled_date=today + timedelta(days=1),
            completion_deadline=today + timedelta(days=3),
        )
        bravo = Task.objects.create(
            user=self.user,
            title="sort fixture bravo",
            priority=Task.Priority.HIGH,
            scheduled_date=None,
            completion_deadline=today + timedelta(days=1),
        )
        charlie = Task.objects.create(
            user=self.user,
            title="sort fixture charlie",
            priority=Task.Priority.MEDIUM,
            scheduled_date=today + timedelta(days=3),
            completion_deadline=None,
        )

        now = timezone.now()
        Task.objects.filter(pk=alpha.pk).update(
            created_at=now - timedelta(days=3)
        )
        Task.objects.filter(pk=bravo.pk).update(
            created_at=now - timedelta(days=2)
        )
        Task.objects.filter(pk=charlie.pk).update(
            created_at=now - timedelta(days=1)
        )

        expected_orders = {
            "title": [alpha.pk, bravo.pk, charlie.pk],
            "-title": [charlie.pk, bravo.pk, alpha.pk],
            "created_at": [alpha.pk, bravo.pk, charlie.pk],
            "-created_at": [charlie.pk, bravo.pk, alpha.pk],
            "priority": [alpha.pk, charlie.pk, bravo.pk],
            "-priority": [bravo.pk, charlie.pk, alpha.pk],
            "scheduled_date": [alpha.pk, charlie.pk, bravo.pk],
            "-scheduled_date": [charlie.pk, alpha.pk, bravo.pk],
            "completion_deadline": [bravo.pk, alpha.pk, charlie.pk],
            "-completion_deadline": [alpha.pk, bravo.pk, charlie.pk],
        }

        for sort, expected_order in expected_orders.items():
            with self.subTest(sort=sort):
                tasks = filtered_tasks_for_user(
                    user=self.user,
                    search="sort fixture",
                    sort=sort,
                )
                actual_order = [task.pk for task in tasks]

                self.assertEqual(actual_order, expected_order)


class TaskServiceTests(TestCase):
    TEST_PASSWORD = "HolidayHome123!"

    def setUp(self):
        self.user = User.objects.create_user(
            email="alice@example.com",
            first_name="Alice",
            last_name="Smith",
            password=self.TEST_PASSWORD,
        )
        self.other_user = User.objects.create_user(
            email="bob@example.com",
            first_name="Bob",
            last_name="Jones",
            password=self.TEST_PASSWORD,
        )

    def test_create_task_persists_all_values_and_returns_created_task(self):
        property_record = Property.objects.create(
            user=self.user,
            name="Hill House",
        )
        scheduled_date = timezone.localdate() + timedelta(days=1)
        completion_deadline = timezone.localdate() + timedelta(days=7)

        task = create_task(
            user=self.user,
            property=property_record,
            issue=None,
            priority=Task.Priority.URGENT,
            title="Arrange roof repair",
            description="Ask the roofer to inspect the west elevation.",
            scheduled_date=scheduled_date,
            completion_deadline=completion_deadline,
        )
        persisted_task = Task.objects.get(pk=task.pk)

        self.assertEqual(persisted_task, task)
        self.assertEqual(persisted_task.user, self.user)
        self.assertEqual(persisted_task.property, property_record)
        self.assertIsNone(persisted_task.issue)
        self.assertEqual(persisted_task.priority, Task.Priority.URGENT)
        self.assertEqual(persisted_task.title, "Arrange roof repair")
        self.assertEqual(
            persisted_task.description,
            "Ask the roofer to inspect the west elevation.",
        )
        self.assertEqual(persisted_task.scheduled_date, scheduled_date)
        self.assertEqual(
            persisted_task.completion_deadline,
            completion_deadline,
        )

    def test_create_task_assigns_each_supported_optional_parent(self):
        property_record = Property.objects.create(
            user=self.user,
            name="Hill House",
        )
        issue = Issue.objects.create(
            user=self.user,
            title="Roof leak",
        )
        parents = {
            "standalone": {"property": None, "issue": None},
            "property": {"property": property_record, "issue": None},
            "issue": {"property": None, "issue": issue},
        }

        for label, parent_values in parents.items():
            with self.subTest(parent=label):
                task = create_task(
                    user=self.user,
                    priority=Task.Priority.LOW,
                    title=f"{label} task",
                    description="",
                    scheduled_date=None,
                    completion_deadline=None,
                    **parent_values,
                )
                task.refresh_from_db()

                self.assertEqual(task.user, self.user)
                self.assertEqual(task.property, parent_values["property"])
                self.assertEqual(task.issue, parent_values["issue"])

    def test_update_task_persists_editable_fields_and_returns_task(self):
        original_property = Property.objects.create(
            user=self.user,
            name="Hill House",
        )
        replacement_issue = Issue.objects.create(
            user=self.user,
            title="Roof leak",
        )
        task = Task.objects.create(
            user=self.user,
            property=original_property,
            priority=Task.Priority.LOW,
            title="Original title",
            description="Original description",
        )
        scheduled_date = timezone.localdate() + timedelta(days=2)
        completion_deadline = timezone.localdate() + timedelta(days=8)

        returned_task = update_task(
            task=task,
            property=None,
            issue=replacement_issue,
            priority=Task.Priority.HIGH,
            title="Updated title",
            description="Updated description",
            scheduled_date=scheduled_date,
            completion_deadline=completion_deadline,
        )
        task.refresh_from_db()

        self.assertIs(returned_task, task)
        self.assertIsNone(task.property)
        self.assertEqual(task.issue, replacement_issue)
        self.assertEqual(task.priority, Task.Priority.HIGH)
        self.assertEqual(task.title, "Updated title")
        self.assertEqual(task.description, "Updated description")
        self.assertEqual(task.scheduled_date, scheduled_date)
        self.assertEqual(task.completion_deadline, completion_deadline)

    def test_update_task_preserves_user_and_lifecycle_fields(self):
        terminated_at = timezone.now() - timedelta(days=2)
        deleted_at = timezone.now() - timedelta(days=1)
        task = Task.objects.create(
            user=self.user,
            state=Task.State.DISMISSED,
            title="Original title",
            terminated_at=terminated_at,
            deleted_at=deleted_at,
        )
        created_at = task.created_at

        update_task(
            task=task,
            property=None,
            issue=None,
            priority=Task.Priority.MEDIUM,
            title="Updated title",
            description="Updated description",
            scheduled_date=None,
            completion_deadline=None,
        )
        task.refresh_from_db()

        self.assertEqual(task.user, self.user)
        self.assertEqual(task.state, Task.State.DISMISSED)
        self.assertEqual(task.created_at, created_at)
        self.assertEqual(task.terminated_at, terminated_at)
        self.assertEqual(task.deleted_at, deleted_at)

    def test_dismiss_task_dismisses_active_task_at_current_time(self):
        task = Task.objects.create(user=self.user, title="Active task")
        dismissed_at = timezone.now() + timedelta(minutes=1)

        with patch("task.services.timezone.now", return_value=dismissed_at):
            returned_task = dismiss_task(task=task)
        task.refresh_from_db()

        self.assertIs(returned_task, task)
        self.assertEqual(task.state, Task.State.DISMISSED)
        self.assertEqual(task.terminated_at, dismissed_at)

    def test_dismiss_task_leaves_terminated_tasks_unchanged(self):
        original_terminated_at = timezone.now() - timedelta(days=1)

        for state in (Task.State.DISMISSED, Task.State.COMPLETED):
            with self.subTest(state=state):
                task = Task.objects.create(
                    user=self.user,
                    state=state,
                    title=f"{state} task",
                    terminated_at=original_terminated_at,
                )

                dismiss_task(task=task)
                task.refresh_from_db()

                self.assertEqual(task.state, state)
                self.assertEqual(task.terminated_at, original_terminated_at)

    def test_complete_task_completes_active_task_at_current_time(self):
        task = Task.objects.create(user=self.user, title="Active task")
        completed_at = timezone.now() + timedelta(minutes=1)

        with patch("task.services.timezone.now", return_value=completed_at):
            returned_task = complete_task(task=task)
        task.refresh_from_db()

        self.assertIs(returned_task, task)
        self.assertEqual(task.state, Task.State.COMPLETED)
        self.assertEqual(task.terminated_at, completed_at)

    def test_complete_task_leaves_terminated_tasks_unchanged(self):
        original_terminated_at = timezone.now() - timedelta(days=1)

        for state in (Task.State.DISMISSED, Task.State.COMPLETED):
            with self.subTest(state=state):
                task = Task.objects.create(
                    user=self.user,
                    state=state,
                    title=f"{state} task",
                    terminated_at=original_terminated_at,
                )

                complete_task(task=task)
                task.refresh_from_db()

                self.assertEqual(task.state, state)
                self.assertEqual(task.terminated_at, original_terminated_at)

    def test_reactivate_task_reactivates_terminated_tasks(self):
        terminated_at = timezone.now() - timedelta(days=1)

        for state in (Task.State.DISMISSED, Task.State.COMPLETED):
            with self.subTest(state=state):
                task = Task.objects.create(
                    user=self.user,
                    state=state,
                    title=f"{state} task",
                    terminated_at=terminated_at,
                )

                returned_task = reactivate_task(task=task)
                task.refresh_from_db()

                self.assertIs(returned_task, task)
                self.assertEqual(task.state, Task.State.ACTIVE)
                self.assertIsNone(task.terminated_at)

    def test_reactivate_task_leaves_active_task_unchanged(self):
        task = Task.objects.create(user=self.user, title="Active task")

        reactivate_task(task=task)
        task.refresh_from_db()

        self.assertEqual(task.state, Task.State.ACTIVE)
        self.assertIsNone(task.terminated_at)

    def test_delete_task_soft_deletes_task_at_current_time(self):
        task = Task.objects.create(user=self.user, title="Task to delete")
        deleted_at = timezone.now() + timedelta(minutes=1)

        with patch("task.services.timezone.now", return_value=deleted_at):
            returned_task = delete_task(task=task)
        task.refresh_from_db()

        self.assertIs(returned_task, task)
        self.assertEqual(task.deleted_at, deleted_at)
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())

    def test_delete_task_preserves_original_deletion_time_on_second_call(self):
        original_deleted_at = timezone.now() - timedelta(days=1)
        task = Task.objects.create(user=self.user, title="Task to delete")

        with patch("task.services.timezone.now", return_value=original_deleted_at):
            delete_task(task=task)
        with patch("task.services.timezone.now", return_value=timezone.now()):
            delete_task(task=task)
        task.refresh_from_db()

        self.assertEqual(task.deleted_at, original_deleted_at)
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())


class TaskViewTests(TestCase):
    TEST_PASSWORD = "HolidayHome123!"
    VALID_DATA = {
        "title": "Arrange roof repair",
        "description": "Ask the roofer to inspect the west elevation.",
        "property": "",
        "issue": "",
        "priority": Task.Priority.HIGH,
        "scheduled_date": "",
        "completion_deadline": "",
    }

    def setUp(self):
        self.user = User.objects.create_user(
            email="alice@example.com",
            first_name="Alice",
            last_name="Smith",
            password=self.TEST_PASSWORD,
        )
        self.other_user = User.objects.create_user(
            email="bob@example.com",
            first_name="Bob",
            last_name="Jones",
            password=self.TEST_PASSWORD,
        )

    def create_task(
        self,
        *,
        user=None,
        title="Arrange roof repair",
        state=Task.State.ACTIVE,
        terminated_at=None,
        deleted_at=None,
    ):
        return Task.objects.create(
            user=user or self.user,
            title=title,
            description="Ask the roofer to inspect the west elevation.",
            priority=Task.Priority.MEDIUM,
            state=state,
            terminated_at=terminated_at,
            deleted_at=deleted_at,
        )

    def task_url(self, name, task):
        return reverse(f"task:{name}", kwargs={"task_id": task.pk})

    def test_task_endpoints_require_login_without_mutating_task(self):
        task = self.create_task()
        original_values = (
            task.title,
            task.state,
            task.terminated_at,
            task.deleted_at,
        )
        endpoints = (
            ("get", reverse("task:tasks"), None),
            ("get", self.task_url("task_detail", task), None),
            ("post", reverse("task:add_task"), self.VALID_DATA),
            ("post", self.task_url("edit_task", task), self.VALID_DATA),
            ("post", self.task_url("dismiss_task", task), None),
            ("post", self.task_url("complete_task", task), None),
            ("post", self.task_url("reactivate_task", task), None),
            ("post", self.task_url("delete_task", task), None),
        )

        for method, url, data in endpoints:
            with self.subTest(method=method, url=url):
                if method == "get":
                    response = self.client.get(url, data=data)
                else:
                    response = self.client.post(url, data=data)
                task.refresh_from_db()

                self.assertRedirects(
                    response,
                    f"{reverse('accounts:login')}?next={url}",
                )
                self.assertEqual(
                    (
                        task.title,
                        task.state,
                        task.terminated_at,
                        task.deleted_at,
                    ),
                    original_values,
                )
                self.assertEqual(Task.objects.count(), 1)

    def test_task_views_reject_unsupported_http_methods(self):
        task = self.create_task()
        self.client.force_login(self.user)
        endpoints = (
            ("post", reverse("task:tasks")),
            ("post", self.task_url("task_detail", task)),
            ("get", reverse("task:add_task")),
            ("get", self.task_url("edit_task", task)),
            ("get", self.task_url("dismiss_task", task)),
            ("get", self.task_url("complete_task", task)),
            ("get", self.task_url("reactivate_task", task)),
            ("get", self.task_url("delete_task", task)),
        )

        for method, url in endpoints:
            with self.subTest(method=method, url=url):
                if method == "get":
                    response = self.client.get(url)
                else:
                    response = self.client.post(url)

                self.assertEqual(response.status_code, 405)

        task.refresh_from_db()
        self.assertEqual(task.state, Task.State.ACTIVE)
        self.assertIsNone(task.deleted_at)

    def test_tasks_view_displays_zero_task_state(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("task:tasks"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "task/tasks.html")
        self.assertEqual(response.context["page_obj"].paginator.count, 0)
        self.assertContains(response, "No tasks yet")

    def test_tasks_view_displays_ten_owned_non_deleted_tasks_only(self):
        own_tasks = [
            self.create_task(title=f"Owned task {number:02}")
            for number in range(10)
        ]
        other_task = self.create_task(
            user=self.other_user,
            title="Another user's task",
        )
        deleted_task = self.create_task(
            title="Soft-deleted task",
            deleted_at=timezone.now(),
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("task:tasks"))
        displayed_tasks = list(response.context["page_obj"].object_list)

        self.assertEqual(displayed_tasks, own_tasks)
        for task in own_tasks:
            self.assertContains(response, task.title)
        self.assertNotContains(response, other_task.title)
        self.assertNotContains(response, deleted_task.title)

    def test_tasks_view_paginates_fifty_one_tasks_as_twenty_twenty_eleven(self):
        for number in range(51):
            self.create_task(title=f"Task {number:02}")
        self.client.force_login(self.user)

        page_sizes = {1: 20, 2: 20, 3: 11}

        for page_number, expected_size in page_sizes.items():
            with self.subTest(page=page_number):
                response = self.client.get(
                    reverse("task:tasks"),
                    {"page": page_number},
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    len(response.context["page_obj"]),
                    expected_size,
                )
                self.assertEqual(
                    response.context["page_obj"].paginator.count,
                    51,
                )

    def test_tasks_view_supplies_clean_unbound_add_form(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("task:tasks"))
        form = response.context["add_task_form"]

        self.assertIsInstance(form, TaskForm)
        self.assertFalse(form.is_bound)
        self.assertEqual(form.errors, {})

    def test_tasks_view_preserves_valid_list_parameters_for_pagination(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("task:tasks"),
            {
                "search": "roof",
                "state": Task.State.ACTIVE,
                "priority": Task.Priority.HIGH,
                "scheduled_period": "next_7_days",
                "deadline_period": "upcoming",
                "sort": "-created_at",
                "page": 2,
            },
        )

        self.assertEqual(
            response.context["list_query"],
            "search=roof&state=active&priority=3&scheduled_period="
            "next_7_days&deadline_period=upcoming&sort=-created_at",
        )

    def test_tasks_view_normalises_invalid_and_default_list_parameters(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("task:tasks"),
            {
                "search": "  roof  ",
                "state": "invalid",
                "priority": "invalid",
                "scheduled_period": "invalid",
                "deadline_period": "invalid",
                "sort": "invalid",
                "page": 4,
            },
        )

        self.assertEqual(response.context["search"], "roof")
        self.assertEqual(response.context["state"], "")
        self.assertEqual(response.context["priority"], "")
        self.assertEqual(response.context["scheduled_period"], "")
        self.assertEqual(response.context["deadline_period"], "")
        self.assertEqual(response.context["sort"], "title")
        self.assertEqual(response.context["list_query"], "search=roof")

    def test_task_detail_view_displays_owned_task_and_clean_edit_form(self):
        task = self.create_task()
        self.client.force_login(self.user)

        response = self.client.get(self.task_url("task_detail", task))
        form = response.context["edit_task_form"]

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "task/task_detail.html")
        self.assertEqual(response.context["task"], task)
        self.assertContains(response, task.title)
        self.assertIsInstance(form, TaskForm)
        self.assertFalse(form.is_bound)
        self.assertEqual(form.instance, task)
        self.assertEqual(form.errors, {})

    def test_task_detail_view_returns_404_for_another_users_task(self):
        task = self.create_task(user=self.other_user)
        self.client.force_login(self.user)

        response = self.client.get(self.task_url("task_detail", task))

        self.assertEqual(response.status_code, 404)

    def test_task_detail_view_returns_404_for_soft_deleted_task(self):
        task = self.create_task(deleted_at=timezone.now())
        self.client.force_login(self.user)

        response = self.client.get(self.task_url("task_detail", task))

        self.assertEqual(response.status_code, 404)

    def test_mutation_views_return_404_for_another_users_task(self):
        active_task = self.create_task(user=self.other_user)
        dismissed_task = self.create_task(
            user=self.other_user,
            title="Another user's dismissed task",
            state=Task.State.DISMISSED,
            terminated_at=timezone.now(),
        )
        self.client.force_login(self.user)
        endpoints = (
            ("edit_task", active_task),
            ("dismiss_task", active_task),
            ("complete_task", active_task),
            ("reactivate_task", dismissed_task),
            ("delete_task", active_task),
        )

        for view_name, task in endpoints:
            with self.subTest(view=view_name):
                response = self.client.post(
                    self.task_url(view_name, task),
                    data=self.VALID_DATA if view_name == "edit_task" else None,
                )

                self.assertEqual(response.status_code, 404)

        active_task.refresh_from_db()
        dismissed_task.refresh_from_db()
        self.assertEqual(active_task.state, Task.State.ACTIVE)
        self.assertIsNone(active_task.deleted_at)
        self.assertEqual(dismissed_task.state, Task.State.DISMISSED)

    def test_edit_task_view_updates_active_task_and_redirects_to_detail(self):
        task = self.create_task(title="Original title")
        property_record = Property.objects.create(
            user=self.user,
            name="Hill House",
        )
        scheduled_date = timezone.localdate() + timedelta(days=1)
        completion_deadline = timezone.localdate() + timedelta(days=7)
        data = {
            "title": "Updated title",
            "description": "Updated description",
            "property": property_record.pk,
            "issue": "",
            "priority": Task.Priority.URGENT,
            "scheduled_date": scheduled_date.isoformat(),
            "completion_deadline": completion_deadline.isoformat(),
        }
        self.client.force_login(self.user)

        response = self.client.post(
            self.task_url("edit_task", task),
            data=data,
        )
        task.refresh_from_db()

        self.assertRedirects(
            response,
            self.task_url("task_detail", task),
        )
        self.assertEqual(task.title, data["title"])
        self.assertEqual(task.description, data["description"])
        self.assertEqual(task.property, property_record)
        self.assertIsNone(task.issue)
        self.assertEqual(task.priority, Task.Priority.URGENT)
        self.assertEqual(task.scheduled_date, scheduled_date)
        self.assertEqual(task.completion_deadline, completion_deadline)

    def test_edit_task_view_rerenders_bound_form_without_partial_update(self):
        task = self.create_task(title="Original title")
        original_values = (
            task.title,
            task.description,
            task.priority,
            task.scheduled_date,
            task.completion_deadline,
        )
        data = self.VALID_DATA.copy()
        data["title"] = ""
        data["description"] = "Attempted update"
        data["priority"] = Task.Priority.URGENT
        self.client.force_login(self.user)

        response = self.client.post(
            self.task_url("edit_task", task),
            data=data,
        )
        task.refresh_from_db()
        form = response.context["edit_task_form"]

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "task/task_detail.html")
        self.assertTrue(form.is_bound)
        self.assertEqual(form.data["title"], data["title"])
        self.assertEqual(form.data["description"], data["description"])
        self.assertEqual(
            form.data["priority"],
            str(data["priority"]),
        )
        self.assertIn("title", form.errors)
        self.assertEqual(
            (
                task.title,
                task.description,
                task.priority,
                task.scheduled_date,
                task.completion_deadline,
            ),
            original_values,
        )

    def test_edit_task_view_returns_404_for_terminated_tasks(self):
        terminated_at = timezone.now() - timedelta(days=1)
        self.client.force_login(self.user)

        for state in (Task.State.DISMISSED, Task.State.COMPLETED):
            with self.subTest(state=state):
                task = self.create_task(
                    title=f"{state} task",
                    state=state,
                    terminated_at=terminated_at,
                )
                response = self.client.post(
                    self.task_url("edit_task", task),
                    data=self.VALID_DATA,
                )

                self.assertEqual(response.status_code, 404)

    def test_dismiss_task_view_dismisses_active_task_and_redirects(self):
        task = self.create_task()
        dismissed_at = timezone.now() + timedelta(minutes=1)
        self.client.force_login(self.user)

        with patch("task.services.timezone.now", return_value=dismissed_at):
            response = self.client.post(self.task_url("dismiss_task", task))
        task.refresh_from_db()

        self.assertRedirects(
            response,
            self.task_url("task_detail", task),
        )
        self.assertEqual(task.state, Task.State.DISMISSED)
        self.assertEqual(task.terminated_at, dismissed_at)

    def test_dismiss_task_view_returns_404_for_terminated_tasks(self):
        terminated_at = timezone.now() - timedelta(days=1)
        self.client.force_login(self.user)

        for state in (Task.State.DISMISSED, Task.State.COMPLETED):
            with self.subTest(state=state):
                task = self.create_task(
                    title=f"{state} task",
                    state=state,
                    terminated_at=terminated_at,
                )
                response = self.client.post(
                    self.task_url("dismiss_task", task)
                )

                self.assertEqual(response.status_code, 404)

    def test_complete_task_view_completes_active_task_and_redirects(self):
        task = self.create_task()
        completed_at = timezone.now() + timedelta(minutes=1)
        self.client.force_login(self.user)

        with patch("task.services.timezone.now", return_value=completed_at):
            response = self.client.post(self.task_url("complete_task", task))
        task.refresh_from_db()

        self.assertRedirects(
            response,
            self.task_url("task_detail", task),
        )
        self.assertEqual(task.state, Task.State.COMPLETED)
        self.assertEqual(task.terminated_at, completed_at)

    def test_complete_task_view_returns_404_for_terminated_tasks(self):
        terminated_at = timezone.now() - timedelta(days=1)
        self.client.force_login(self.user)

        for state in (Task.State.COMPLETED, Task.State.DISMISSED):
            with self.subTest(state=state):
                task = self.create_task(
                    title=f"{state} task",
                    state=state,
                    terminated_at=terminated_at,
                )
                response = self.client.post(
                    self.task_url("complete_task", task)
                )

                self.assertEqual(response.status_code, 404)

    def test_reactivate_task_view_reactivates_terminated_tasks_and_redirects(self):
        terminated_at = timezone.now() - timedelta(days=1)
        self.client.force_login(self.user)

        for state in (Task.State.DISMISSED, Task.State.COMPLETED):
            with self.subTest(state=state):
                task = self.create_task(
                    title=f"{state} task",
                    state=state,
                    terminated_at=terminated_at,
                )
                response = self.client.post(
                    self.task_url("reactivate_task", task)
                )
                task.refresh_from_db()

                self.assertRedirects(
                    response,
                    self.task_url("task_detail", task),
                )
                self.assertEqual(task.state, Task.State.ACTIVE)
                self.assertIsNone(task.terminated_at)

    def test_reactivate_task_view_returns_404_for_active_task(self):
        task = self.create_task()
        self.client.force_login(self.user)

        response = self.client.post(self.task_url("reactivate_task", task))

        self.assertEqual(response.status_code, 404)

    def test_delete_task_view_soft_deletes_each_lifecycle_state_and_redirects(self):
        terminated_at = timezone.now() - timedelta(days=1)
        deleted_at = timezone.now() + timedelta(minutes=1)
        self.client.force_login(self.user)

        for state in Task.State.values:
            with self.subTest(state=state):
                task = self.create_task(
                    title=f"{state} task",
                    state=state,
                    terminated_at=(
                        None if state == Task.State.ACTIVE else terminated_at
                    ),
                )
                with patch(
                    "task.services.timezone.now",
                    return_value=deleted_at,
                ):
                    response = self.client.post(
                        self.task_url("delete_task", task)
                    )
                task.refresh_from_db()

                self.assertRedirects(response, reverse("task:tasks"))
                self.assertEqual(task.deleted_at, deleted_at)
                self.assertTrue(Task.objects.filter(pk=task.pk).exists())

    def test_soft_deleted_tasks_are_inaccessible_from_task_endpoints(self):
        deleted_at = timezone.now()
        active_task = self.create_task(deleted_at=deleted_at)
        dismissed_task = self.create_task(
            title="Soft-deleted dismissed task",
            state=Task.State.DISMISSED,
            terminated_at=timezone.now() - timedelta(days=1),
            deleted_at=deleted_at,
        )
        self.client.force_login(self.user)
        endpoints = (
            ("get", "task_detail", active_task, None),
            ("post", "edit_task", active_task, self.VALID_DATA),
            ("post", "dismiss_task", active_task, None),
            ("post", "complete_task", active_task, None),
            ("post", "reactivate_task", dismissed_task, None),
            ("post", "delete_task", active_task, None),
        )

        for method, view_name, task, data in endpoints:
            with self.subTest(view=view_name):
                if method == "get":
                    response = self.client.get(
                        self.task_url(view_name, task),
                        data=data,
                    )
                else:
                    response = self.client.post(
                        self.task_url(view_name, task),
                        data=data,
                    )

                self.assertEqual(response.status_code, 404)

    def test_add_task_view_with_valid_data_creates_task_and_assigns_to_correct_user(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("task:add_task"),
            data=self.VALID_DATA,
        )   

        task = Task.objects.get(title=self.VALID_DATA["title"])

        self.assertEqual(task.user, self.user)
        self.assertRedirects(
            response,
            reverse(
                "task:task_detail",
                kwargs={"task_id": task.pk}
            ),
        )

    def test_add_task_view_with_invalid_data_returns_bound_form_with_error_and_does_not_create_task(self):
        data = self.VALID_DATA.copy()
        data["title"] = ""

        self.client.force_login(self.user)

        url = f"{reverse('task:add_task')}?search=call_plumber&sort=-created_at"

        response = self.client.post(url, data=data)

        self.assertEqual(response.status_code, 200)
        self.assertIn("title", response.context["add_task_form"].errors)
        self.assertTrue(response.context["add_task_form"].is_bound)
        self.assertEqual(response.context["search"], "call_plumber")
        self.assertEqual(response.context["sort"], "-created_at")
        self.assertContains(response, "bootstrap.Modal.getOrCreateInstance")
        self.assertEqual(Task.objects.count(), 0)
        self.assertEqual(response.context["list_query"], "search=call_plumber&sort=-created_at")
