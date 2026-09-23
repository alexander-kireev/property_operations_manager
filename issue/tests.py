from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from property.models import Property
from task.forms import TaskForm
from task.models import Task
from task.selectors import tasks_for_issue

from .forms import IssueForm
from .models import Issue
from .selectors import filtered_issues_for_user, issues_for_user
from .services import (
    create_issue,
    delete_issue,
    dismiss_issue,
    reactivate_issue,
    resolve_issue,
    update_issue,
)


class IssueTestMixin:
    password = "HolidayHome123!"

    def create_user(self, email="alice@example.com"):
        return User.objects.create_user(
            email=email,
            first_name="Alice",
            last_name="Smith",
            password=self.password,
        )

    def create_property(self, user, name="Hill House", **values):
        return Property.objects.create(user=user, name=name, **values)

    def create_issue(self, user, title="Roof leak", **values):
        return Issue.objects.create(user=user, title=title, **values)

    def create_task(self, user, issue, title="Arrange contractor", **values):
        return Task.objects.create(user=user, issue=issue, title=title, **values)


class IssueModelTests(IssueTestMixin, TestCase):
    def test_defaults_relationship_and_string_value(self):
        issue = self.create_issue(self.create_user())

        self.assertEqual(issue.state, Issue.State.ACTIVE)
        self.assertEqual(issue.priority, Issue.Priority.LOW)
        self.assertIsNone(issue.property)
        self.assertIsNone(issue.resolution_deadline)
        self.assertIsNone(issue.terminated_at)
        self.assertIsNone(issue.deleted_at)
        self.assertEqual(str(issue), "Roof leak")

    def test_issue_exposes_linked_tasks(self):
        user = self.create_user()
        issue = self.create_issue(user)
        task = self.create_task(user, issue)

        self.assertEqual(list(issue.tasks.all()), [task])


class IssueFormTests(IssueTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.property = self.create_property(self.user)

    def valid_data(self):
        return {
            "title": "Roof leak",
            "description": "Water entering upstairs",
            "property": self.property.pk,
            "priority": Issue.Priority.URGENT,
            "resolution_deadline": (
                timezone.localdate() + timedelta(days=4)
            ).isoformat(),
        }

    def test_valid_form_exposes_only_editable_fields(self):
        form = IssueForm(data=self.valid_data(), user=self.user)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            list(form.fields),
            ["title", "description", "property", "priority", "resolution_deadline"],
        )
        self.assertEqual(form.fields["resolution_deadline"].label, "Resolve by")

    def test_issue_forms_use_searchable_property_picker_and_target_date_copy(self):
        self.client.force_login(self.user)
        self.create_issue(self.user, property=self.property)

        response = self.client.get(reverse("issue:issues"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-searchable-select', count=4)
        self.assertContains(response, "Resolve by")
        self.assertContains(response, "the issue will not resolve automatically", count=2)

    def test_another_users_property_is_rejected(self):
        other_property = self.create_property(
            self.create_user("bob@example.com"), "Other House"
        )
        data = self.valid_data()
        data["property"] = other_property.pk

        form = IssueForm(data=data, user=self.user)

        self.assertFalse(form.is_valid())
        self.assertIn("property", form.errors)

    def test_soft_deleted_property_is_rejected(self):
        self.property.deleted_at = timezone.now()
        self.property.save(update_fields=["deleted_at"])

        form = IssueForm(data=self.valid_data(), user=self.user)

        self.assertFalse(form.is_valid())
        self.assertIn("property", form.errors)

    def test_edit_keeps_current_inactive_property_available(self):
        issue = self.create_issue(self.user, property=self.property)
        self.property.state = Property.State.DEACTIVATED
        self.property.save(update_fields=["state"])

        form = IssueForm(data=self.valid_data(), user=self.user, instance=issue)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertIn(self.property, form.fields["property"].queryset)


class IssueSelectorTests(IssueTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.other_user = self.create_user("bob@example.com")
        self.property = self.create_property(self.user, address="12 Hill Road")

    def test_issues_for_user_scopes_owner_and_soft_deletion(self):
        visible = self.create_issue(self.user, "Visible")
        self.create_issue(self.other_user, "Other user")
        self.create_issue(self.user, "Deleted", deleted_at=timezone.now())

        self.assertEqual(list(issues_for_user(user=self.user)), [visible])

    def test_search_covers_issue_and_property_text(self):
        title_match = self.create_issue(self.user, "Broken gutter")
        property_match = self.create_issue(
            self.user, "Unrelated title", property=self.property
        )

        self.assertEqual(
            list(filtered_issues_for_user(user=self.user, search="gutter")),
            [title_match],
        )
        self.assertEqual(
            list(filtered_issues_for_user(user=self.user, search="Hill Road")),
            [property_match],
        )

    def test_filters_state_priority_and_property(self):
        wanted = self.create_issue(
            self.user,
            property=self.property,
            state=Issue.State.RESOLVED,
            priority=Issue.Priority.HIGH,
        )
        self.create_issue(self.user, "Other")

        result = filtered_issues_for_user(
            user=self.user,
            state=Issue.State.RESOLVED,
            priority=Issue.Priority.HIGH,
            property_id=self.property.pk,
        )

        self.assertEqual(list(result), [wanted])

    def test_deadline_filters_and_null_last_sort(self):
        overdue = self.create_issue(
            self.user,
            "Overdue",
            resolution_deadline=timezone.localdate() - timedelta(days=1),
        )
        no_deadline = self.create_issue(self.user, "No deadline")

        self.assertEqual(
            list(filtered_issues_for_user(user=self.user, deadline_period="overdue")),
            [overdue],
        )
        self.assertEqual(
            list(
                filtered_issues_for_user(
                    user=self.user, sort="resolution_deadline"
                )
            ),
            [overdue, no_deadline],
        )

    def test_tasks_for_issue_includes_states_but_excludes_deleted(self):
        issue = self.create_issue(self.user)
        active = self.create_task(self.user, issue, "Active")
        completed = self.create_task(
            self.user, issue, "Completed", state=Task.State.COMPLETED
        )
        self.create_task(
            self.user, issue, "Deleted", deleted_at=timezone.now()
        )
        self.create_task(self.other_user, issue, "Wrong owner")

        self.assertEqual(
            list(tasks_for_issue(user=self.user, issue=issue)),
            [active, completed],
        )


class IssueServiceTests(IssueTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.property = self.create_property(self.user)

    def test_create_and_update_issue(self):
        issue = create_issue(
            user=self.user,
            property=self.property,
            priority=Issue.Priority.HIGH,
            title="Roof",
            description="Leak",
            resolution_deadline=timezone.localdate(),
        )
        update_issue(
            issue=issue,
            property=None,
            priority=Issue.Priority.LOW,
            title="Updated roof",
            description="Updated",
            resolution_deadline=None,
        )

        issue.refresh_from_db()
        self.assertEqual(issue.title, "Updated roof")
        self.assertEqual(issue.priority, Issue.Priority.LOW)
        self.assertIsNone(issue.property)

    def test_resolve_without_cascade_leaves_tasks_active(self):
        issue = self.create_issue(self.user)
        task = self.create_task(self.user, issue)

        resolve_issue(issue=issue)
        task.refresh_from_db()

        self.assertEqual(issue.state, Issue.State.RESOLVED)
        self.assertIsNotNone(issue.terminated_at)
        self.assertEqual(task.state, Task.State.ACTIVE)

    def test_resolve_with_cascade_dismisses_only_active_tasks(self):
        issue = self.create_issue(self.user)
        active = self.create_task(self.user, issue, "Active")
        completed = self.create_task(
            self.user, issue, "Completed", state=Task.State.COMPLETED
        )

        resolve_issue(issue=issue, dismiss_linked_tasks=True)
        active.refresh_from_db()
        completed.refresh_from_db()

        self.assertEqual(active.state, Task.State.DISMISSED)
        self.assertEqual(completed.state, Task.State.COMPLETED)

    def test_reactivate_does_not_reactivate_tasks(self):
        issue = self.create_issue(self.user)
        task = self.create_task(self.user, issue)

        dismiss_issue(issue=issue, dismiss_linked_tasks=True)
        reactivate_issue(issue=issue)
        task.refresh_from_db()

        self.assertEqual(issue.state, Issue.State.ACTIVE)
        self.assertIsNone(issue.terminated_at)
        self.assertEqual(task.state, Task.State.DISMISSED)

    def test_delete_optionally_soft_deletes_linked_tasks(self):
        issue = self.create_issue(self.user)
        task = self.create_task(self.user, issue)

        delete_issue(issue=issue, delete_linked_tasks=True)
        task.refresh_from_db()

        self.assertIsNotNone(issue.deleted_at)
        self.assertIsNotNone(task.deleted_at)

    def test_delete_without_cascade_leaves_task_visible(self):
        issue = self.create_issue(self.user)
        task = self.create_task(self.user, issue)

        delete_issue(issue=issue)
        task.refresh_from_db()

        self.assertIsNone(task.deleted_at)


class IssueViewTests(IssueTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.client.force_login(self.user)
        self.property = self.create_property(self.user)
        self.issue = self.create_issue(
            self.user, property=self.property, priority=Issue.Priority.URGENT
        )

    def test_confirmation_keeps_issue_title_and_linked_task_choice_in_body(self):
        self.issue.title = "Roof " + "X" * 90
        self.issue.save(update_fields=["title"])
        self.create_task(self.user, self.issue)

        response = self.client.get(reverse("issue:issues"))

        self.assertContains(response, 'id="resolveIssueModalLabel">Resolve issue?</h2>')
        self.assertContains(response, 'class="modal-context-value">' + self.issue.title)
        self.assertContains(response, 'id="resolveLinkedTasks"')
        self.assertContains(response, 'class="btn btn-danger" type="submit">Delete issue')

    def test_issue_list_defaults_to_active_and_can_show_terminal_states(self):
        resolved = self.create_issue(self.user, "Resolved issue", state=Issue.State.RESOLVED)
        dismissed = self.create_issue(self.user, "Dismissed issue", state=Issue.State.DISMISSED)

        for query, expected in (
            ({}, [self.issue]),
            ({"state": Issue.State.RESOLVED}, [resolved]),
            ({"state": Issue.State.DISMISSED}, [dismissed]),
            ({"state": "all"}, [self.issue, resolved, dismissed]),
        ):
            with self.subTest(query=query):
                response = self.client.get(reverse("issue:issues"), query)
                self.assertCountEqual(response.context["page_obj"].object_list, expected)

    def test_terminal_only_issue_list_offers_all_states(self):
        self.issue.state = Issue.State.RESOLVED
        self.issue.save(update_fields=["state"])

        response = self.client.get(reverse("issue:issues"))

        self.assertContains(response, "No active issues")
        self.assertContains(response, "Show all states")

    def issue_data(self, **overrides):
        data = {
            "title": "Boiler losing pressure",
            "description": "Pressure drops overnight",
            "property": self.property.pk,
            "priority": Issue.Priority.HIGH,
            "resolution_deadline": (
                timezone.localdate() + timedelta(days=3)
            ).isoformat(),
        }
        data.update(overrides)
        return data

    def task_data(self, **overrides):
        data = {
            "title": "Call contractor",
            "description": "Arrange inspection",
            "priority": Task.Priority.HIGH,
            "scheduled_date": "",
            "completion_deadline": "",
        }
        data.update(overrides)
        return data

    def test_issues_view_renders_selected_issue_and_tasks(self):
        task = self.create_task(self.user, self.issue)

        response = self.client.get(
            reverse("issue:issues"),
            {"selected": self.issue.pk, "tab": "tasks"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_issue"], self.issue)
        self.assertEqual(list(response.context["selected_tasks"]), [task])
        self.assertEqual(response.context["active_tab"], "tasks")

    def test_genuine_empty_state_uses_full_width_onboarding(self):
        self.issue.delete()

        response = self.client.get(reverse("issue:issues"))

        self.assertContains(response, "No issues yet")
        self.assertContains(response, "Add your first issue")
        self.assertNotContains(response, "Search issues")
        self.assertNotContains(response, "No issues match your filters")

    def test_filtered_empty_state_keeps_controls_and_clear_action(self):
        response = self.client.get(
            reverse("issue:issues"),
            {"search": "nothing will match this"},
        )

        self.assertContains(response, "Search issues")
        self.assertContains(response, "No issues match your filters")
        self.assertContains(response, "Clear filters")
        self.assertNotContains(response, "Add your first issue")

    def test_issues_view_paginates_twenty_at_a_time(self):
        Issue.objects.all().delete()
        for number in range(45):
            self.create_issue(self.user, f"Issue {number:02}")

        response = self.client.get(
            reverse("issue:issues"),
            {"search": "Issue", "page": 2},
        )

        self.assertEqual(len(response.context["page_obj"]), 20)
        self.assertEqual(response.context["page_obj"].paginator.num_pages, 3)
        self.assertContains(response, "Page 2 of 3")
        self.assertContains(response, "?search=Issue&amp;page=1")
        self.assertContains(response, "?search=Issue&amp;page=3")

    def test_issues_view_normalises_query_parameters(self):
        response = self.client.get(
            reverse("issue:issues"),
            {"search": "  roof  ", "state": "wrong", "sort": "wrong"},
        )

        self.assertEqual(response.context["search"], "roof")
        self.assertEqual(response.context["state"], "")
        self.assertEqual(response.context["sort"], "resolution_deadline")
        self.assertEqual(response.context["list_query"], "search=roof")

    def test_add_issue_valid_and_invalid_flows(self):
        response = self.client.post(reverse("issue:add_issue"), self.issue_data())
        created = Issue.objects.get(title="Boiler losing pressure")
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"selected={created.pk}", response.url)

        post_response = self.client.post(
            reverse("issue:add_issue"), self.issue_data(title="")
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["add_issue_form"].is_bound)
        self.assertEqual(response.context["open_modal"], "addIssueModal")

    def test_edit_issue_updates_active_issue(self):
        response = self.client.post(
            reverse("issue:edit_issue", args=[self.issue.pk]),
            self.issue_data(title="Updated issue"),
        )

        self.issue.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.issue.title, "Updated issue")

    def test_invalid_edit_issue_redirects_and_restores_bound_form(self):
        original_title = self.issue.title

        post_response = self.client.post(
            reverse("issue:edit_issue", args=[self.issue.pk]),
            self.issue_data(title=""),
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn(f"selected={self.issue.pk}", post_response.url)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)
        self.issue.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_issue"], self.issue)
        self.assertEqual(response.context["open_modal"], "editIssueModal")
        self.assertIn("title", response.context["edit_issue_form"].errors)
        self.assertEqual(self.issue.title, original_title)

    def test_lifecycle_view_applies_explicit_cascade_choice(self):
        task = self.create_task(self.user, self.issue)

        response = self.client.post(
            reverse("issue:resolve_issue", args=[self.issue.pk]),
            {"affect_linked_tasks": "yes"},
        )

        self.issue.refresh_from_db()
        task.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.issue.state, Issue.State.RESOLVED)
        self.assertEqual(task.state, Task.State.DISMISSED)

    def test_delete_issue_can_delete_linked_tasks(self):
        task = self.create_task(self.user, self.issue)

        self.client.post(
            reverse("issue:delete_issue", args=[self.issue.pk]),
            {"affect_linked_tasks": "yes"},
        )
        self.issue.refresh_from_db()
        task.refresh_from_db()

        self.assertIsNotNone(self.issue.deleted_at)
        self.assertIsNotNone(task.deleted_at)

    def test_add_issue_task_locks_parent_and_returns_to_tasks_tab(self):
        response = self.client.post(
            reverse("issue:add_issue_task", args=[self.issue.pk]),
            self.task_data(property=self.property.pk),
        )
        task = Task.objects.get(title="Call contractor")

        self.assertEqual(task.issue, self.issue)
        self.assertIsNone(task.property)
        self.assertEqual(response.status_code, 302)
        self.assertIn("tab=tasks", response.url)

    def test_invalid_issue_task_returns_bound_form_to_tasks_tab(self):
        post_response = self.client.post(
            reverse("issue:add_issue_task", args=[self.issue.pk]),
            self.task_data(title=""),
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn(f"selected={self.issue.pk}", post_response.url)
        self.assertIn("tab=tasks", post_response.url)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["add_task_form"].is_bound)
        self.assertEqual(response.context["active_tab"], "tasks")
        self.assertEqual(response.context["open_modal"], "addIssueTaskModal")
        self.assertFalse(Task.objects.exists())

    def test_add_issue_task_rejects_terminated_and_other_users_issue(self):
        other_issue = self.create_issue(self.create_user("bob@example.com"))
        self.issue.state = Issue.State.RESOLVED
        self.issue.terminated_at = timezone.now()
        self.issue.save(update_fields=["state", "terminated_at"])

        for issue in (self.issue, other_issue):
            with self.subTest(issue=issue.pk):
                response = self.client.post(
                    reverse("issue:add_issue_task", args=[issue.pk]),
                    self.task_data(),
                )
                self.assertEqual(response.status_code, 404)

    def test_edit_issue_task_keeps_parent_when_no_relink_requested(self):
        task = self.create_task(self.user, self.issue)

        response = self.client.post(
            reverse("issue:edit_issue_task", args=[self.issue.pk, task.pk]),
            self.task_data(title="Updated task"),
        )
        task.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(task.title, "Updated task")
        self.assertEqual(task.issue, self.issue)
        self.assertIsNone(task.property)

    def test_cross_user_issue_mutations_return_404(self):
        other_issue = self.create_issue(self.create_user("bob@example.com"))
        endpoints = (
            "edit_issue",
            "resolve_issue",
            "dismiss_issue",
            "reactivate_issue",
            "delete_issue",
        )

        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.post(
                    reverse(f"issue:{endpoint}", args=[other_issue.pk]),
                    self.issue_data(),
                )
                self.assertEqual(response.status_code, 404)

    def test_mutation_views_reject_get_requests(self):
        task = self.create_task(self.user, self.issue)
        urls = (
            reverse("issue:add_issue"),
            reverse("issue:edit_issue", args=[self.issue.pk]),
            reverse("issue:resolve_issue", args=[self.issue.pk]),
            reverse("issue:dismiss_issue", args=[self.issue.pk]),
            reverse("issue:reactivate_issue", args=[self.issue.pk]),
            reverse("issue:delete_issue", args=[self.issue.pk]),
            reverse("issue:add_issue_task", args=[self.issue.pk]),
            reverse("issue:edit_issue_task", args=[self.issue.pk, task.pk]),
        )

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)

    def test_soft_deleted_issue_is_not_selectable_or_mutable(self):
        self.issue.deleted_at = timezone.now()
        self.issue.save(update_fields=["deleted_at"])

        response = self.client.get(
            reverse("issue:issues"),
            {"selected": self.issue.pk},
        )
        mutation = self.client.post(
            reverse("issue:delete_issue", args=[self.issue.pk])
        )

        self.assertIsNone(response.context["selected_issue"])
        self.assertEqual(mutation.status_code, 404)

    def test_invalid_issue_task_edit_returns_bound_form(self):
        task = self.create_task(self.user, self.issue)

        post_response = self.client.post(
            reverse("issue:edit_issue_task", args=[self.issue.pk, task.pk]),
            self.task_data(title=""),
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn(f"selected={self.issue.pk}", post_response.url)
        self.assertIn("tab=tasks", post_response.url)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["edit_task_form"].is_bound)
        self.assertEqual(response.context["edit_task"], task)
        self.assertEqual(response.context["active_tab"], "tasks")
        self.assertEqual(response.context["open_modal"], "editIssueTaskModal")


class IssueAuthenticationTests(IssueTestMixin, TestCase):
    def test_issue_endpoints_require_authentication(self):
        user = self.create_user()
        issue = self.create_issue(user)
        task = self.create_task(user, issue)
        endpoints = (
            ("get", reverse("issue:issues")),
            ("post", reverse("issue:add_issue")),
            ("post", reverse("issue:edit_issue", args=[issue.pk])),
            ("post", reverse("issue:resolve_issue", args=[issue.pk])),
            ("post", reverse("issue:dismiss_issue", args=[issue.pk])),
            ("post", reverse("issue:reactivate_issue", args=[issue.pk])),
            ("post", reverse("issue:delete_issue", args=[issue.pk])),
            ("post", reverse("issue:add_issue_task", args=[issue.pk])),
            ("post", reverse("issue:edit_issue_task", args=[issue.pk, task.pk])),
        )

        for method, url in endpoints:
            with self.subTest(url=url):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 302)


class LockedTaskFormTests(IssueTestMixin, TestCase):
    def test_parent_issue_mode_removes_relationship_fields(self):
        user = self.create_user()
        issue = self.create_issue(user)

        form = TaskForm(user=user, parent_issue=issue)

        self.assertNotIn("property", form.fields)
        self.assertNotIn("issue", form.fields)


class TaskIssueReturnTests(IssueTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.client.force_login(self.user)
        self.issue = self.create_issue(self.user)

    def test_task_lifecycle_action_accepts_safe_issue_return_url(self):
        task = self.create_task(self.user, self.issue)
        next_url = (
            f"{reverse('issue:issues')}?selected={self.issue.pk}&tab=tasks"
        )

        response = self.client.post(
            reverse("task:complete_task", args=[task.pk]),
            {"next": next_url},
        )

        self.assertRedirects(response, next_url, fetch_redirect_response=False)

    def test_task_lifecycle_action_rejects_external_return_url(self):
        task = self.create_task(self.user, self.issue)

        response = self.client.post(
            reverse("task:complete_task", args=[task.pk]),
            {"next": "https://malicious.example/issues/"},
        )

        self.assertRedirects(
            response,
            f"{reverse('task:tasks')}?selected={task.pk}",
            fetch_redirect_response=False,
        )
