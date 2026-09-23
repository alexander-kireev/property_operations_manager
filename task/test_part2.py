from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from issue.models import Issue
from property.models import Property
from task.forms import TaskForm
from task.models import Task


class TaskRelationshipAndDateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="part2@example.com",
            first_name="Alex",
            last_name="Smith",
            password="TestPassword123!",
        )
        self.client.force_login(self.user)
        self.property = Property.objects.create(user=self.user, name="Cedar House")
        self.issue = Issue.objects.create(user=self.user, title="Roof leak")
        self.other_issue = Issue.objects.create(user=self.user, title="Heating fault")
        self.task = Task.objects.create(user=self.user, issue=self.issue, title="Call contractor")

    def task_data(self, **changes):
        data = {
            "title": "Call contractor",
            "description": "Arrange inspection",
            "priority": Task.Priority.HIGH,
            "scheduled_date": "",
            "completion_deadline": "",
            "relationship_type": "issue",
            "property": "",
            "issue": str(self.issue.pk),
        }
        data.update(changes)
        return data

    def test_past_dates_and_reversed_order_save_without_changing_state(self):
        today = timezone.localdate()
        data = self.task_data(
            scheduled_date=(today - timedelta(days=1)).isoformat(),
            completion_deadline=(today - timedelta(days=3)).isoformat(),
        )
        response = self.client.post(reverse("task:edit_task", args=[self.task.pk]), data)
        self.task.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.task.scheduled_date, today - timedelta(days=1))
        self.assertEqual(self.task.completion_deadline, today - timedelta(days=3))
        self.assertEqual(self.task.state, Task.State.ACTIVE)

    def test_issue_task_can_move_to_property_and_redirect_to_task(self):
        response = self.client.post(
            reverse("issue:edit_issue_task", args=[self.issue.pk, self.task.pk]),
            self.task_data(
                relationship_type="property",
                property=str(self.property.pk),
                issue=str(self.issue.pk),
            ),
        )
        self.task.refresh_from_db()

        self.assertEqual(self.task.property, self.property)
        self.assertIsNone(self.task.issue)
        self.assertEqual(
            response.url,
            f"{reverse('task:tasks')}?selected={self.task.pk}&moved=1",
        )
        self.assertContains(self.client.get(response.url), "no longer linked to the previous issue")

    def test_issue_task_can_move_to_another_issue_or_standalone(self):
        response = self.client.post(
            reverse("issue:edit_issue_task", args=[self.issue.pk, self.task.pk]),
            self.task_data(issue=str(self.other_issue.pk)),
        )
        self.task.refresh_from_db()
        self.assertEqual(self.task.issue, self.other_issue)
        self.assertIn("moved=1", response.url)

        response = self.client.post(
            reverse("task:edit_task", args=[self.task.pk]),
            self.task_data(relationship_type="standalone", issue=str(self.other_issue.pk)),
        )
        self.task.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.task.issue)
        self.assertIsNone(self.task.property)

    def test_other_users_and_unavailable_parents_are_rejected(self):
        other_user = User.objects.create_user(
            email="other-part2@example.com",
            first_name="Sam",
            last_name="Jones",
            password="TestPassword123!",
        )
        other_issue = Issue.objects.create(user=other_user, title="Private issue")
        self.other_issue.state = Issue.State.RESOLVED
        self.other_issue.terminated_at = timezone.now()
        self.other_issue.save(update_fields=["state", "terminated_at"])

        for issue in (other_issue, self.other_issue):
            with self.subTest(issue=issue.pk):
                form = TaskForm(
                    data=self.task_data(issue=str(issue.pk)),
                    user=self.user,
                    instance=self.task,
                )
                self.assertFalse(form.is_valid())
                self.assertIn("issue", form.errors)

    def test_existing_resolved_issue_can_be_retained_during_unrelated_edit(self):
        self.issue.state = Issue.State.RESOLVED
        self.issue.terminated_at = timezone.now()
        self.issue.save(update_fields=["state", "terminated_at"])

        form = TaskForm(
            data=self.task_data(title="Updated title"),
            user=self.user,
            instance=self.task,
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["issue"], self.issue)

    def test_completed_task_cannot_be_moved_from_issue(self):
        self.task.state = Task.State.COMPLETED
        self.task.save(update_fields=["state"])

        response = self.client.post(
            reverse("issue:edit_issue_task", args=[self.issue.pk, self.task.pk]),
            self.task_data(relationship_type="standalone", issue=""),
        )
        self.assertEqual(response.status_code, 404)

    def test_task_forms_render_stable_relationship_slot_and_searchable_choices(self):
        response = self.client.get(reverse("task:tasks"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-relationship-panel="standalone"')
        self.assertContains(response, "No linked property or issue")
        self.assertContains(response, 'data-searchable-select', count=4)
        self.assertContains(response, "js/searchable-select.js")
