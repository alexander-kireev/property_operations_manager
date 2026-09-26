from datetime import time, timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from event.models import Event
from issue.models import Issue
from note.models import Note
from task.models import Task


class DashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com", password="A-strong-password-123",
            first_name="Owner", last_name="One",
        )
        self.other = User.objects.create_user(
            email="other@example.com", password="A-strong-password-123",
            first_name="Other", last_name="Two",
        )
        self.client.force_login(self.user)
        self.today = timezone.localdate()
        self.task = Task.objects.create(user=self.user, title="Call contractor")
        Task.objects.create(user=self.other, title="Private task")

    def test_dashboard_data_is_private(self):
        response = self.client.get(reverse("pages:dashboard_data"))
        self.assertEqual(response.status_code, 200)
        titles = [item["title"] for item in response.json()["records"]["task"]]
        self.assertEqual(titles, ["Call contractor"])

    def test_dashboard_data_exposes_task_and_issue_deadlines(self):
        deadline = self.today + timedelta(days=2)
        self.task.completion_deadline = deadline
        self.task.save(update_fields=["completion_deadline"])
        issue = Issue.objects.create(user=self.user, title="Faulty lock", resolution_deadline=deadline)
        response = self.client.get(reverse("pages:dashboard_data"))
        records = response.json()["records"]
        self.assertEqual(records["task"][0]["due"], deadline.isoformat())
        self.assertEqual(records["issue"][0]["id"], issue.pk)
        self.assertEqual(records["issue"][0]["due"], deadline.isoformat())

    def test_dashboard_sets_csrf_cookie_for_actions(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.get(reverse("pages:dashboard"))
        self.assertIn("csrftoken", response.cookies)
        token = response.cookies["csrftoken"].value
        response = client.post(reverse("pages:dashboard_action"), {
            "action": "add", "kind": "note", "content": "Check access",
        }, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)

    def test_dashboard_uses_month_and_year_controls_without_week_view(self):
        response = self.client.get(reverse("pages:dashboard"))
        self.assertContains(response, 'id="calendarMonth"')
        self.assertContains(response, 'id="calendarYear"')
        self.assertContains(response, 'id="selectedDayNumber"')
        self.assertNotContains(response, 'data-view="week"')

    def test_dashboard_has_selected_day_tabs_and_toast(self):
        response = self.client.get(reverse("pages:dashboard"))
        for tab in ("tasks", "deadlines", "events"):
            self.assertContains(response, f'data-day-tab="{tab}"')
        self.assertContains(response, 'id="dashboardToast"')

    def test_dashboard_switches_between_day_and_notes_with_add_control_in_operations(self):
        response = self.client.get(reverse("pages:dashboard"))
        html = response.content.decode()
        self.assertLess(html.index('id="dashboardAddToggle"'), html.index('id="calendarGrid"'))
        self.assertContains(response, 'id="dayViewToggle"')
        self.assertContains(response, 'id="notesViewToggle"')
        self.assertContains(response, 'id="notesView" role="tabpanel" aria-labelledby="notesViewToggle" hidden')
        self.assertContains(response, 'id="notesList"')
        self.assertNotContains(response, 'id="notesToggle"')

    def test_schedule_task_and_keep_its_deadline(self):
        self.task.completion_deadline = self.today + timedelta(days=5)
        self.task.save(update_fields=["completion_deadline"])
        date = self.today + timedelta(days=2)
        response = self.client.post(reverse("pages:dashboard_action"), {
            "action": "date", "kind": "task", "id": self.task.pk, "date": date.isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.scheduled_date, date)
        self.assertEqual(self.task.completion_deadline, self.today + timedelta(days=5))

    def test_move_task_deadline_without_rescheduling_task(self):
        scheduled = self.today + timedelta(days=1)
        deadline = self.today + timedelta(days=4)
        self.task.scheduled_date = scheduled
        self.task.completion_deadline = self.today + timedelta(days=2)
        self.task.save(update_fields=["scheduled_date", "completion_deadline"])
        response = self.client.post(reverse("pages:dashboard_action"), {
            "action": "deadline", "kind": "task", "id": self.task.pk, "date": deadline.isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.scheduled_date, scheduled)
        self.assertEqual(self.task.completion_deadline, deadline)

    def test_move_issue_deadline(self):
        issue = Issue.objects.create(user=self.user, title="Faulty lock", resolution_deadline=self.today)
        deadline = self.today + timedelta(days=3)
        response = self.client.post(reverse("pages:dashboard_action"), {
            "action": "deadline", "kind": "issue", "id": issue.pk, "date": deadline.isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        issue.refresh_from_db()
        self.assertEqual(issue.resolution_deadline, deadline)

    def test_deadline_rejects_invalid_date_and_other_users_record(self):
        invalid = self.client.post(reverse("pages:dashboard_action"), {
            "action": "deadline", "kind": "task", "id": self.task.pk, "date": "not-a-date",
        })
        self.assertEqual(invalid.status_code, 400)
        other_task = Task.objects.get(user=self.other)
        private = self.client.post(reverse("pages:dashboard_action"), {
            "action": "deadline", "kind": "task", "id": other_task.pk,
            "date": self.today.isoformat(),
        })
        self.assertEqual(private.status_code, 404)

    def test_event_cannot_use_deadline_action(self):
        event = Event.objects.create(user=self.user, title="Visit", scheduled_date=self.today + timedelta(days=2), all_day=True)
        response = self.client.post(reverse("pages:dashboard_action"), {
            "action": "deadline", "kind": "event", "id": event.pk, "date": self.today.isoformat(),
        })
        self.assertEqual(response.status_code, 400)

    def test_cannot_change_another_users_task(self):
        other_task = Task.objects.get(user=self.other)
        response = self.client.post(reverse("pages:dashboard_action"), {
            "action": "date", "kind": "task", "id": other_task.pk,
            "date": self.today.isoformat(),
        })
        self.assertEqual(response.status_code, 404)

    def test_event_cannot_move_into_past(self):
        event = Event.objects.create(user=self.user, title="Visit", scheduled_date=self.today + timedelta(days=2), all_day=True)
        response = self.client.post(reverse("pages:dashboard_action"), {
            "action": "date", "kind": "event", "id": event.pk,
            "date": (self.today - timedelta(days=1)).isoformat(),
        })
        self.assertEqual(response.status_code, 400)
        event.refresh_from_db()
        self.assertEqual(event.scheduled_date, self.today + timedelta(days=2))

    def test_timed_event_edit_preserves_time_when_date_changes(self):
        event = Event.objects.create(
            user=self.user, title="Visit", scheduled_date=self.today + timedelta(days=2),
            all_day=False, start_time=time(14, 0), end_time=time(15, 0),
        )
        target = self.today + timedelta(days=3)
        response = self.client.post(reverse("pages:dashboard_action"), {
            "action": "edit", "kind": "event", "id": event.pk, "title": event.title,
            "description": "", "property": "", "scheduled_date": target.isoformat(),
            "start_time": "14:00", "end_time": "15:00",
        })
        self.assertEqual(response.status_code, 200)
        event.refresh_from_db()
        self.assertEqual(event.scheduled_date, target)
        self.assertEqual(event.start_time, time(14, 0))
        self.assertEqual(event.end_time, time(15, 0))

    def test_cancel_event_from_dashboard(self):
        event = Event.objects.create(user=self.user, title="Visit", scheduled_date=self.today + timedelta(days=2), all_day=True)
        response = self.client.post(reverse("pages:dashboard_action"), {
            "action": "cancel", "kind": "event", "id": event.pk,
        })
        self.assertEqual(response.status_code, 200)
        event.refresh_from_db()
        self.assertEqual(event.state, Event.State.CANCELLED)
        self.assertIsNotNone(event.terminated_at)
        active_titles = [item["title"] for item in self.client.get(reverse("pages:dashboard_data")).json()["records"]["event"]]
        self.assertNotIn("Visit", active_titles)

    def test_cannot_cancel_another_users_event(self):
        event = Event.objects.create(user=self.other, title="Private visit", scheduled_date=self.today + timedelta(days=2), all_day=True)
        response = self.client.post(reverse("pages:dashboard_action"), {
            "action": "cancel", "kind": "event", "id": event.pk,
        })
        self.assertEqual(response.status_code, 404)
        event.refresh_from_db()
        self.assertEqual(event.state, Event.State.SCHEDULED)

    def test_add_note_is_general_and_private(self):
        response = self.client.post(reverse("pages:dashboard_action"), {
            "action": "add", "kind": "note", "content": "Check access",
        })
        self.assertEqual(response.status_code, 200)
        note = Note.objects.get(pk=response.json()["id"])
        self.assertEqual(note.user, self.user)
        self.assertIsNone(note.contact)

    def test_add_issue_uses_model_form_validation(self):
        response = self.client.post(reverse("pages:dashboard_action"), {
            "action": "add", "kind": "issue", "title": "Tap leak",
            "description": "", "property": "", "priority": Issue.Priority.HIGH,
            "resolution_deadline": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Issue.objects.filter(user=self.user, title="Tap leak").exists())

    def test_add_task_and_event(self):
        task_response = self.client.post(reverse("pages:dashboard_action"), {
            "action": "add", "kind": "task", "title": "Book visit",
            "description": "", "relationship_type": "standalone",
            "property": "", "issue": "", "priority": Task.Priority.MEDIUM,
            "scheduled_date": "", "completion_deadline": "",
        })
        self.assertEqual(task_response.status_code, 200)
        self.assertTrue(Task.objects.filter(user=self.user, title="Book visit").exists())
        event_response = self.client.post(reverse("pages:dashboard_action"), {
            "action": "add", "kind": "event", "title": "Access visit",
            "description": "", "property": "", "scheduled_date": (self.today + timedelta(days=1)).isoformat(),
            "all_day": "on", "start_time": "", "end_time": "",
        })
        self.assertEqual(event_response.status_code, 200)
        self.assertTrue(Event.objects.filter(user=self.user, title="Access visit").exists())
