from datetime import timedelta
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.db.models import DateField, IntegerField, Value
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from event.models import Event
from issue.models import Issue
from task.models import Task

from .forms import PropertyForm
from .models import Property


class PropertyModelTests(TestCase):
    TEST_PASSWORD = "HolidayHome123!"

    def create_user(self, email):
        return User.objects.create_user(
            email=email,
            first_name="Test",
            last_name="User",
            password=self.TEST_PASSWORD,
        )

    def test_property_name_is_case_insensitively_unique_per_user(self):
        user = self.create_user("alice@example.com")
        Property.objects.create(user=user, name="Hill House")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Property.objects.create(user=user, name="HILL HOUSE")

    def test_different_users_can_use_the_same_property_name(self):
        user_1 = self.create_user("alice@example.com")
        user_2 = self.create_user("bob@example.com")

        Property.objects.create(user=user_1, name="Hill House")
        Property.objects.create(user=user_2, name="HILL HOUSE")

        self.assertEqual(Property.objects.count(), 2)

    def test_deleted_property_name_can_be_reused_by_same_user(self):
        user = self.create_user("alice@example.com")
        deleted_property = Property.objects.create(user=user, name="Hill House")
        deleted_property.deleted_at = timezone.now()
        deleted_property.save(update_fields=["deleted_at"])

        Property.objects.create(user=user, name="HILL HOUSE")

        self.assertEqual(Property.objects.count(), 2)


class PropertyFormTests(TestCase):
    TEST_PASSWORD = "HolidayHome123!"
    VALID_DATA = {
        "name": "Hill House",
        "description": "Three-bedroom managed property.",
        "address": "12 Green Lane, London",
    }

    def setUp(self):
        self.user = User.objects.create_user(
            email="alice@example.com",
            first_name="Alice",
            last_name="Smith",
            password=self.TEST_PASSWORD,
        )

    def test_duplicate_name_for_user_is_rejected_case_insensitively(self):
        Property.objects.create(user=self.user, name="Hill House")
        data = self.VALID_DATA.copy()
        data["name"] = "HILL HOUSE"

        form = PropertyForm(data=data, user=self.user)

        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_editing_property_without_changing_its_name_is_valid(self):
        property_record = Property.objects.create(
            user=self.user,
            name=self.VALID_DATA["name"],
        )

        form = PropertyForm(
            data=self.VALID_DATA,
            user=self.user,
            instance=property_record,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_deleted_property_name_can_be_reused(self):
        Property.objects.create(
            user=self.user,
            name="Hill House",
            deleted_at=timezone.now(),
        )
        data = self.VALID_DATA.copy()
        data["name"] = "HILL HOUSE"

        form = PropertyForm(data=data, user=self.user)

        self.assertTrue(form.is_valid(), form.errors)


class PropertyViewTests(TestCase):
    TEST_PASSWORD = "HolidayHome123!"
    VALID_DATA = {
        "name": "Hill House",
        "description": "Three-bedroom managed property.",
        "address": "12 Green Lane, London",
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

    def create_property(
        self,
        *,
        user=None,
        name="Hill House",
        state=Property.State.ACTIVE,
        address="12 Green Lane, London",
    ):
        return Property.objects.create(
            user=user or self.user,
            name=name,
            description="Managed property.",
            address=address,
            state=state,
        )

    def test_list_summary_uses_real_counts_and_next_upcoming_event(self):
        property_record = self.create_property()
        issue = Issue.objects.create(user=self.user, property=property_record, title="Open issue")
        Issue.objects.create(user=self.user, property=property_record, title="Resolved", state=Issue.State.RESOLVED)
        Task.objects.create(user=self.user, property=property_record, title="Direct task")
        Task.objects.create(user=self.user, issue=issue, title="Issue task")
        Task.objects.create(user=self.user, property=property_record, title="Done", state=Task.State.COMPLETED)
        tomorrow = timezone.localdate() + timedelta(days=1)
        Event.objects.create(user=self.user, property=property_record, title="Visit", scheduled_date=tomorrow, all_day=True)
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:properties"))
        listed = response.context["page_obj"].object_list[0]

        self.assertEqual(listed.open_issues, 1)
        self.assertEqual(listed.open_direct_tasks + listed.open_issue_tasks, 2)
        self.assertEqual(listed.next_event_date, tomorrow)
        self.assertContains(response, "1 issue · 2 tasks")
        self.assertNotContains(response, "Contacts</div>")

    def test_list_summary_handles_zero_and_large_counts(self):
        empty = self.create_property(name="Empty")
        busy = self.create_property(name="Busy")
        Issue.objects.bulk_create(Issue(user=self.user, property=busy, title=f"Issue {index}") for index in range(1000))
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:properties"))
        listed = {record.pk: record for record in response.context["page_obj"].object_list}

        self.assertEqual(listed[empty.pk].open_issues, 0)
        self.assertEqual(listed[busy.pk].open_issues, 1000)

    def test_mocked_summary_values_render_without_placeholder(self):
        self.create_property()
        self.client.force_login(self.user)
        for count in (0, 999, 1000, 100000):
            with self.subTest(count=count), patch("property.views.with_work_summary") as summary:
                summary.side_effect = lambda records: records.annotate(
                    open_issues=Value(count, output_field=IntegerField()),
                    open_direct_tasks=Value(count, output_field=IntegerField()),
                    open_issue_tasks=Value(0, output_field=IntegerField()),
                    next_event_date=Value(None, output_field=DateField()),
                )
                response = self.client.get(reverse("property:properties"))
                self.assertContains(response, f"{count} issues")

    def test_list_edit_and_state_actions_preserve_filters_and_page(self):
        property_record = self.create_property(name="Oak House")
        self.client.force_login(self.user)
        query = "?return_to=list&search=Oak&state=all&sort=-name&page=2"
        expected = f"{reverse('property:properties')}?search=Oak&state=all&sort=-name&page=2"

        response = self.client.post(reverse("property:edit_property", args=[property_record.pk]) + query, {
            "name": "Oak House", "description": "Updated", "address": "10 Oak Road",
        })
        self.assertRedirects(response, expected, fetch_redirect_response=False)
        response = self.client.post(reverse("property:deactivate_property", args=[property_record.pk]) + query)
        self.assertRedirects(response, expected, fetch_redirect_response=False)
        response = self.client.post(reverse("property:reactivate_property", args=[property_record.pk]) + query)
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_invalid_list_edit_reopens_shared_modal(self):
        property_record = self.create_property(name="Oak House")
        self.client.force_login(self.user)

        response = self.client.post(reverse("property:edit_property", args=[property_record.pk]) + "?return_to=list&search=Oak", {
            "name": "", "description": "Updated", "address": "10 Oak Road",
        }, follow=True)

        self.assertContains(response, 'data-modal-auto-open="listEditPropertyModal"')
        self.assertContains(response, "This field is required")

    def test_property_list_requires_login(self):
        response = self.client.get(reverse("property:properties"))

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('property:properties')}",
        )

    def test_property_list_only_contains_current_users_properties(self):
        own_property = self.create_property(name="Hill House")
        other_property = self.create_property(
            user=self.other_user,
            name="River Cottage",
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:properties"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, own_property.name)
        self.assertNotContains(response, other_property.name)

    def test_deleted_property_is_excluded_from_property_list(self):
        visible_property = self.create_property(name="Hill House")
        deleted_property = self.create_property(name="Deleted House")
        deleted_property.deleted_at = timezone.now()
        deleted_property.save(update_fields=["deleted_at"])
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:properties"))

        self.assertContains(response, visible_property.name)
        self.assertNotContains(response, deleted_property.name)

    def test_search_matches_property_name_or_address(self):
        name_match = self.create_property(name="Hill House")
        address_match = self.create_property(
            name="City Flat",
            address="22 Hill Road, London",
        )
        self.create_property(name="River Cottage", address="1 Water Lane")
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("property:properties"),
            {"search": "hill"},
        )
        properties = list(response.context["page_obj"].object_list)

        self.assertEqual(properties, [address_match, name_match])

    def test_state_filter_only_returns_matching_properties(self):
        active_property = self.create_property(name="Active House")
        self.create_property(
            name="Old House",
            state=Property.State.DEACTIVATED,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("property:properties"),
            {"state": Property.State.ACTIVE},
        )

        self.assertEqual(
            list(response.context["page_obj"].object_list),
            [active_property],
        )

    def test_property_list_defaults_to_active_and_can_show_deactivated(self):
        active = self.create_property(name="Active House")
        deactivated = self.create_property(
            name="Old House",
            state=Property.State.DEACTIVATED,
        )
        self.client.force_login(self.user)

        for query, expected in (
            ({}, [active]),
            ({"state": Property.State.DEACTIVATED}, [deactivated]),
            ({"state": "all"}, [active, deactivated]),
        ):
            with self.subTest(query=query):
                response = self.client.get(reverse("property:properties"), query)
                self.assertCountEqual(response.context["page_obj"].object_list, expected)

    def test_deactivated_only_property_list_offers_all_states(self):
        self.create_property(state=Property.State.DEACTIVATED)
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:properties"))

        self.assertContains(response, "No active properties")
        self.assertContains(response, "Show all states")

    def test_all_supported_sort_options_return_expected_order(self):
        alpha = self.create_property(name="Alpha House")
        zebra = self.create_property(name="Zebra House")
        earlier = timezone.now() - timedelta(days=2)
        later = timezone.now() - timedelta(days=1)
        Property.objects.filter(pk=alpha.pk).update(created_at=earlier)
        Property.objects.filter(pk=zebra.pk).update(created_at=later)
        self.client.force_login(self.user)

        expected_orders = {
            "name": [alpha.pk, zebra.pk],
            "-name": [zebra.pk, alpha.pk],
            "created_at": [alpha.pk, zebra.pk],
            "-created_at": [zebra.pk, alpha.pk],
        }

        for sort, expected_order in expected_orders.items():
            with self.subTest(sort=sort):
                response = self.client.get(
                    reverse("property:properties"),
                    {"sort": sort},
                )
                actual_order = [
                    property_record.pk
                    for property_record in response.context["page_obj"].object_list
                ]

                self.assertEqual(actual_order, expected_order)

    def test_property_list_is_paginated_at_twenty_properties(self):
        for property_number in range(21):
            self.create_property(name=f"Property {property_number:02}")
        self.client.force_login(self.user)

        first_page = self.client.get(reverse("property:properties"))
        second_page = self.client.get(
            reverse("property:properties"),
            {"page": 2},
        )

        self.assertEqual(len(first_page.context["page_obj"]), 20)
        self.assertEqual(len(second_page.context["page_obj"]), 1)

    def test_pagination_preserves_search_filter_and_sort_parameters(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("property:properties"),
            {
                "search": "House",
                "state": Property.State.ACTIVE,
                "sort": "-name",
                "page": 2,
            },
        )

        self.assertEqual(
            response.context["list_query"],
            "search=House&state=active&sort=-name",
        )

    def test_valid_creation_assigns_user_and_redirects_to_detail(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("property:add_property"),
            data=self.VALID_DATA,
        )
        property_record = Property.objects.get(name=self.VALID_DATA["name"])

        self.assertEqual(property_record.user, self.user)
        self.assertRedirects(
            response,
            reverse(
                "property:property_detail",
                kwargs={"property_id": property_record.pk},
            ),
        )

    def test_invalid_creation_reopens_modal_and_preserves_list_state(self):
        self.create_property(name="Hill House")
        self.client.force_login(self.user)
        url = f"{reverse('property:add_property')}?search=Hill&sort=-name"
        data = self.VALID_DATA.copy()
        data["name"] = "HILL HOUSE"

        post_response = self.client.post(url, data=data)

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("search=Hill", post_response.url)
        self.assertIn("sort=-name", post_response.url)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("name", response.context["add_property_form"].errors)
        self.assertEqual(response.context["search"], "Hill")
        self.assertEqual(response.context["sort"], "-name")
        self.assertContains(
            response,
            'data-modal-auto-open="addPropertyModal"',
        )
        self.assertEqual(Property.objects.count(), 1)

    def test_property_detail_only_allows_owning_user(self):
        own_property = self.create_property(name="Hill House")
        other_property = self.create_property(
            user=self.other_user,
            name="River Cottage",
        )
        self.client.force_login(self.user)

        own_response = self.client.get(
            reverse(
                "property:property_detail",
                kwargs={"property_id": own_property.pk},
            )
        )
        other_response = self.client.get(
            reverse(
                "property:property_detail",
                kwargs={"property_id": other_property.pk},
            )
        )

        self.assertEqual(own_response.status_code, 200)
        self.assertTemplateUsed(own_response, "property/property_detail.html")
        self.assertEqual(other_response.status_code, 404)

    def test_property_work_links_are_full_rows(self):
        property_record = self.create_property()
        issue = Issue.objects.create(user=self.user, property=property_record, title="Entry phone")
        task = Task.objects.create(user=self.user, property=property_record, title="Arrange access")
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:property_detail", args=[property_record.pk]))
        self.assertContains(response, f'href="{reverse("issue:issues")}?state=all&amp;selected={issue.pk}&amp;open=detail"')
        self.assertContains(response, f'href="{reverse("task:tasks")}?state=all&amp;selected={task.pk}&amp;open=detail"')
        self.assertContains(response, 'class="navbar-nav app-mobile-menu d-lg-none"')
        self.assertContains(response, 'class="app-mobile-logout" type="submit">Log out</button>')

    def test_mobile_property_header_keeps_long_name_status_and_actions_together(self):
        name = "Northgate Mews and Gardens Residential Building"
        property_record = self.create_property(name=name)
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:property_detail", args=[property_record.pk]))

        self.assertContains(response, 'class="property-command-header"')
        self.assertNotContains(response, 'class="property-detail-header"')
        self.assertContains(response, 'class="property-mobile-back-row"')
        self.assertContains(response, 'class="property-heading-title-row"')
        self.assertContains(response, f'<h2 class="h3 mb-1">{name}</h2>')
        self.assertContains(response, 'class="property-heading-status work-pill work-pill--active"')
        self.assertContains(response, 'class="property-heading-description"')
        self.assertContains(response, 'class="property-heading-actions"')
        self.assertContains(response, 'aria-label="Property actions"')

    def test_property_rows_show_existing_work_and_event_flags(self):
        property_record = self.create_property()
        Issue.objects.create(
            user=self.user, property=property_record, title="Urgent issue",
            priority=Issue.Priority.URGENT, resolution_deadline=timezone.localdate() - timedelta(days=1),
        )
        Task.objects.create(
            user=self.user, property=property_record, title="High task",
            priority=Task.Priority.HIGH, completion_deadline=timezone.localdate() + timedelta(days=1),
        )
        Event.objects.create(
            user=self.user, property=property_record, title="Site visit",
            scheduled_date=timezone.localdate() + timedelta(days=1), all_day=True,
            user_participation_required=True, user_presence_required=True,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:property_detail", args=[property_record.pk]))

        self.assertContains(response, 'name="records_type"')
        self.assertContains(response, 'name="records_scope"')
        self.assertContains(response, 'work-pill--priority-4')
        self.assertContains(response, 'work-pill--overdue')
        self.assertContains(response, 'work-pill--priority-3')
        self.assertContains(response, 'work-pill--soon')
        self.assertContains(response, 'property-event-badge">Scheduled')
        self.assertContains(response, 'property-presence-badge">Presence required')

    def test_related_records_default_to_current_records(self):
        property_record = self.create_property()
        Task.objects.create(user=self.user, property=property_record, title="Book plumber")
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:property_detail", args=[property_record.pk]))

        self.assertContains(response, '1 record')
        self.assertContains(response, 'Book plumber')
        self.assertContains(response, 'value="current" selected')

    def test_command_centre_shows_one_related_records_view(self):
        property_record = self.create_property()
        self.client.force_login(self.user)

        for url in (reverse("property:properties"), reverse("property:property_detail", args=[property_record.pk])):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.context["selected_property"], property_record)
                self.assertContains(response, 'Related records')
                self.assertNotContains(response, 'data-property-tab=')
                self.assertContains(response, 'data-workspace-scroll-root="properties"')

    def test_related_records_link_to_canonical_details(self):
        property_record = self.create_property()
        Issue.objects.create(user=self.user, property=property_record, title="Repair tap", description="Water is leaking.")
        Task.objects.create(user=self.user, property=property_record, title="Book plumber", description="Call the contractor.")
        Event.objects.create(
            user=self.user, property=property_record, title="Inspection", description="Meet at the entrance.",
            scheduled_date=timezone.localdate() + timedelta(days=1), all_day=True,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:property_detail", args=[property_record.pk]))

        self.assertContains(response, 'class="property-related-record"', count=3)
        self.assertNotContains(response, '<details class="property-record">')
        self.assertContains(response, 'Repair tap')
        self.assertContains(response, 'Book plumber')
        self.assertContains(response, 'Inspection')

    def test_heading_shows_description_above_related_records(self):
        property_record = self.create_property()
        property_record.description = "Long property context. " * 30
        property_record.save(update_fields=["description"])
        Issue.objects.create(user=self.user, property=property_record, title="Entry phone")
        Task.objects.create(user=self.user, property=property_record, title="Arrange access")
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:property_detail", args=[property_record.pk]))

        self.assertContains(response, 'class="property-heading-description"')
        self.assertContains(response, 'Related records')
        self.assertContains(response, '2 records')
        self.assertContains(response, 'data-property-description-preview')
        self.assertContains(response, 'data-bs-target="#propertyDescriptionModal"')
        self.assertContains(response, 'class="modal-body property-description-full"')
        self.assertNotContains(response, "At a glance")

    def test_related_records_list_all_current_types_without_duplicates(self):
        property_record = self.create_property()
        for number in range(3):
            Issue.objects.create(user=self.user, property=property_record, title=f"Issue {number}")
            Task.objects.create(user=self.user, property=property_record, title=f"Task {number}")
            Event.objects.create(
                user=self.user, property=property_record, title=f"Event {number}",
                scheduled_date=timezone.localdate() + timedelta(days=number + 1), all_day=True,
            )
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:property_detail", args=[property_record.pk]))
        html = response.content.decode()
        self.assertEqual(html.count('class="property-related-record"'), 9)
        self.assertNotIn('<details class="property-record">', html)
        for number in range(3):
            self.assertIn(f"Issue {number}", html)
            self.assertIn(f"Task {number}", html)
            self.assertIn(f"Event {number}", html)

    def test_history_contains_terminated_records_but_not_deleted_or_other_users_records(self):
        property_record = self.create_property()
        now = timezone.now()
        Issue.objects.create(user=self.user, property=property_record, title="Fixed leak", state=Issue.State.RESOLVED, terminated_at=now)
        Task.objects.create(user=self.user, property=property_record, title="Finished job", state=Task.State.COMPLETED, terminated_at=now - timedelta(days=1))
        Event.objects.create(user=self.user, property=property_record, title="Completed visit", scheduled_date=timezone.localdate(), all_day=True, state=Event.State.OCCURRED, terminated_at=now - timedelta(days=2))
        Issue.objects.create(user=self.user, property=property_record, title="Hidden issue", state=Issue.State.RESOLVED, terminated_at=now, deleted_at=now)
        Issue.objects.create(user=self.other_user, property=property_record, title="Other user issue", state=Issue.State.RESOLVED, terminated_at=now)
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:property_detail", args=[property_record.pk]), {"records_scope": "past"})

        self.assertEqual([entry["item"].title for entry in response.context["related_page"]], ["Fixed leak", "Finished job", "Completed visit"])
        self.assertContains(response, 'property-outcome--resolved">Resolved')
        self.assertContains(response, 'property-outcome--completed">Completed')
        self.assertContains(response, 'property-outcome--occurred">Occurred')
        self.assertNotContains(response, "Hidden issue")
        self.assertNotContains(response, "Other user issue")

    def test_related_records_filter_by_type_scope_and_search(self):
        property_record = self.create_property()
        Issue.objects.create(user=self.user, property=property_record, title="Leaking pipe", description="Kitchen")
        Task.objects.create(user=self.user, property=property_record, title="Call plumber")
        Event.objects.create(
            user=self.user, property=property_record, title="Past visit",
            scheduled_date=timezone.localdate(), all_day=True,
            state=Event.State.OCCURRED, terminated_at=timezone.now(),
        )
        self.client.force_login(self.user)
        url = reverse("property:property_detail", args=[property_record.pk])

        current = self.client.get(url)
        self.assertEqual(current.context["related_page"].paginator.count, 2)
        past = self.client.get(url, {"records_scope": "past"})
        self.assertEqual([entry["item"].title for entry in past.context["related_page"]], ["Past visit"])
        issues = self.client.get(url, {"records_type": "issue", "records_search": "kitchen"})
        self.assertEqual([entry["item"].title for entry in issues.context["related_page"]], ["Leaking pipe"])

    def test_add_buttons_open_forms_on_the_property_page(self):
        property_record = self.create_property()
        self.client.force_login(self.user)
        response = self.client.get(reverse("property:property_detail", args=[property_record.pk]))
        for kind, modal in (
            ("issue", "propertyAddIssueModal"),
            ("task", "propertyAddTaskModal"),
            ("event", "propertyAddEventModal"),
        ):
            with self.subTest(kind=kind):
                self.assertContains(response, f'data-bs-target="#{modal}"')
                self.assertContains(response, reverse("property:add_property_record", args=[property_record.pk, kind]))
                self.assertEqual(response.context[f"property_add_{kind}_form"].initial["property"], property_record.pk)

    def test_property_add_creates_each_record_without_leaving_property(self):
        property_record = self.create_property()
        self.client.force_login(self.user)
        cases = (
            ("issue", Issue, {"title": "Repair window", "priority": Issue.Priority.HIGH}),
            ("task", Task, {"title": "Call contractor", "priority": Task.Priority.HIGH}),
            ("event", Event, {
                "title": "Site visit",
                "scheduled_date": (timezone.localdate() + timedelta(days=1)).isoformat(),
                "all_day": "on",
            }),
        )
        for kind, model, data in cases:
            with self.subTest(kind=kind):
                response = self.client.post(
                    reverse("property:add_property_record", args=[property_record.pk, kind]), data,
                )
                self.assertRedirects(
                    response,
                    reverse("property:property_detail", args=[property_record.pk])
                    + f"?records_type={kind}&records_scope=current&records_sort=recent",
                    fetch_redirect_response=False,
                )
                self.assertTrue(model.objects.filter(user=self.user, property=property_record, title=data["title"]).exists())

    def test_invalid_property_add_reopens_same_modal_with_entered_values(self):
        property_record = self.create_property()
        self.client.force_login(self.user)
        for kind, modal in (
            ("issue", "propertyAddIssueModal"),
            ("task", "propertyAddTaskModal"),
            ("event", "propertyAddEventModal"),
        ):
            with self.subTest(kind=kind):
                response = self.client.post(
                    reverse("property:add_property_record", args=[property_record.pk, kind]),
                    {"title": "", "description": "Keep this text"},
                )
                restored = self.client.get(response.url)
                self.assertIn(f"/properties/{property_record.pk}/?form_state=", response.url)
                self.assertEqual(restored.context["property_record_modal"], modal)
                self.assertEqual(restored.context[f"property_add_{kind}_form"].data["description"], "Keep this text")

    def test_property_add_ignores_tampered_property_field(self):
        origin = self.create_property(name="Origin")
        destination = self.create_property(name="Destination")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("property:add_property_record", args=[origin.pk, "task"]),
            {"title": "Stay here", "property": destination.pk, "relationship_type": "standalone", "priority": Task.Priority.LOW},
        )
        self.assertEqual(response.status_code, 302)
        task = Task.objects.get(title="Stay here")
        self.assertEqual(task.property, origin)
        self.assertIsNone(task.issue)

    def test_creating_from_property_returns_to_its_new_record(self):
        property_record = self.create_property()
        self.client.force_login(self.user)
        cases = (
            ("issue:add_issue", Issue, "issue", {
                "title": "Repair window", "property": property_record.pk,
                "priority": Issue.Priority.HIGH,
            }),
            ("task:add_task", Task, "task", {
                "title": "Call contractor", "property": property_record.pk,
                "relationship_type": "property", "priority": Task.Priority.HIGH,
            }),
            ("event:add_event", Event, "event", {
                "title": "Site visit", "property": property_record.pk,
                "scheduled_date": (timezone.localdate() + timedelta(days=1)).isoformat(),
                "all_day": "on",
            }),
        )
        for route, model, kind, data in cases:
            with self.subTest(route=route):
                response = self.client.post(reverse(route), {**data, "return_property": property_record.pk})
                self.assertRedirects(
                    response,
                    reverse("property:property_detail", args=[property_record.pk])
                    + f"?records_type={kind}&records_scope=current&records_sort=recent",
                    fetch_redirect_response=False,
                )
                self.assertTrue(model.objects.filter(user=self.user, property=property_record, title=data["title"]).exists())

    def test_invalid_property_origin_form_keeps_return_destination(self):
        property_record = self.create_property()
        self.client.force_login(self.user)
        response = self.client.post(reverse("issue:add_issue"), {
            "title": "", "property": property_record.pk,
            "return_property": property_record.pk,
        })
        restored = self.client.get(response.url)
        self.assertEqual(restored.context["open_modal"], "addIssueModal")
        self.assertEqual(restored.context["return_property_id"], property_record.pk)
        self.assertContains(restored, f'name="return_property" value="{property_record.pk}"')

    def test_property_origin_does_not_redirect_when_record_is_moved_elsewhere(self):
        origin = self.create_property(name="Origin")
        destination = self.create_property(name="Destination")
        self.client.force_login(self.user)
        response = self.client.post(reverse("task:add_task"), {
            "title": "New task", "property": destination.pk,
            "relationship_type": "property", "return_property": origin.pk,
            "priority": Task.Priority.LOW,
        })
        task = Task.objects.get(title="New task")
        self.assertEqual(response.url, f"{reverse('task:tasks')}?selected={task.pk}")

    def test_related_records_are_paginated_without_losing_filters(self):
        property_record = self.create_property()
        for number in range(27):
            Task.objects.create(user=self.user, property=property_record, title=f"Task {number:02d}")
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:property_detail", args=[property_record.pk]), {
            "records_type": "task", "records_sort": "title", "records_page": "2",
        })

        self.assertEqual(response.context["related_page"].paginator.count, 27)
        self.assertEqual(len(response.context["related_page"]), 2)
        self.assertContains(response, "Task 25")
        self.assertContains(response, "Task 26")
        self.assertContains(response, "records_type=task&amp;records_scope=current&amp;records_sort=title&amp;records_page=1")

    def test_property_task_quick_action_returns_to_property_workspace(self):
        property_record = self.create_property()
        task = Task.objects.create(user=self.user, property=property_record, title="Book visit")
        self.client.force_login(self.user)
        next_url = reverse("property:property_detail", args=[property_record.pk]) + "?tab=work"

        response = self.client.post(reverse("task:complete_task", args=[task.pk]), {"next": next_url})

        self.assertRedirects(response, next_url, fetch_redirect_response=False)
        task.refresh_from_db()
        self.assertEqual(task.state, Task.State.COMPLETED)

    def test_property_issue_and_event_quick_actions_return_to_property(self):
        property_record = self.create_property()
        issue = Issue.objects.create(user=self.user, property=property_record, title="Repair tap")
        event = Event.objects.create(user=self.user, property=property_record, title="Inspection", scheduled_date=timezone.localdate() + timedelta(days=1), all_day=True)
        self.client.force_login(self.user)

        for action_url, next_tab in (
            (reverse("issue:resolve_issue", args=[issue.pk]), "work"),
            (reverse("event:cancel_event", args=[event.pk]), "schedule"),
        ):
            with self.subTest(action_url=action_url):
                next_url = reverse("property:property_detail", args=[property_record.pk]) + f"?tab={next_tab}"
                response = self.client.post(action_url, {"next": next_url})
                self.assertRedirects(response, next_url, fetch_redirect_response=False)

    def test_related_edit_links_open_existing_edit_modals(self):
        property_record = self.create_property()
        issue = Issue.objects.create(user=self.user, property=property_record, title="Repair tap")
        task = Task.objects.create(user=self.user, property=property_record, title="Book visit")
        event = Event.objects.create(user=self.user, property=property_record, title="Inspection", scheduled_date=timezone.localdate() + timedelta(days=1), all_day=True)
        self.client.force_login(self.user)

        for route, record, modal in (
            ("issue:issues", issue, "editIssueModal"),
            ("task:tasks", task, "editTaskModal"),
            ("event:events", event, "editEventModal"),
        ):
            with self.subTest(route=route):
                response = self.client.get(reverse(route), {"selected": record.pk, "open": "edit"})
                self.assertContains(response, modal)
                self.assertEqual(response.context["open_modal"], modal)

    def test_deactivated_property_has_no_related_quick_actions(self):
        property_record = self.create_property(state=Property.State.DEACTIVATED)
        Issue.objects.create(user=self.user, property=property_record, title="Retained issue")
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:property_detail", args=[property_record.pk]), {"tab": "work"})

        self.assertContains(response, "Retained issue")
        self.assertNotContains(response, 'data-verb="Resolve"')

    def test_related_action_cannot_return_to_another_property(self):
        source = self.create_property(name="Source House")
        other = self.create_property(name="Other House")
        task = Task.objects.create(user=self.user, property=source, title="Book visit")
        self.client.force_login(self.user)
        wrong_next = reverse("property:property_detail", args=[other.pk]) + "?tab=work"

        response = self.client.post(reverse("task:complete_task", args=[task.pk]), {"next": wrong_next})

        self.assertRedirects(response, reverse("task:tasks") + f"?selected={task.pk}", fetch_redirect_response=False)

    def test_property_detail_query_actions_mark_the_correct_modal_to_open(self):
        property_record = self.create_property()
        self.client.force_login(self.user)
        url = reverse(
            "property:property_detail",
            kwargs={"property_id": property_record.pk},
        )

        for parameter, modal_id in (
            ("edit", "editPropertyModal"),
            ("deactivate", "deactivatePropertyModal"),
            ("confirm_delete", "deletePropertyModal"),
        ):
            with self.subTest(parameter=parameter):
                response = self.client.get(url, {parameter: "1"})
                self.assertContains(
                    response,
                    f'data-modal-auto-open="{modal_id}"',
                )

    def test_deleted_property_detail_returns_404(self):
        property_record = self.create_property()
        property_record.deleted_at = timezone.now()
        property_record.save(update_fields=["deleted_at"])
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "property:property_detail",
                kwargs={"property_id": property_record.pk},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_valid_edit_updates_property(self):
        property_record = self.create_property()
        self.client.force_login(self.user)
        updated_data = {
            "name": "Updated House",
            "description": "Updated description.",
            "address": "20 Updated Road",
        }

        response = self.client.post(
            reverse(
                "property:edit_property",
                kwargs={"property_id": property_record.pk},
            ),
            data=updated_data,
        )
        property_record.refresh_from_db()

        self.assertRedirects(
            response,
            reverse(
                "property:property_detail",
                kwargs={"property_id": property_record.pk},
            ),
        )
        self.assertEqual(property_record.name, updated_data["name"])
        self.assertEqual(property_record.description, updated_data["description"])
        self.assertEqual(property_record.address, updated_data["address"])

    def test_duplicate_name_edit_is_rejected(self):
        property_record = self.create_property(name="Hill House")
        self.create_property(name="River Cottage")
        self.client.force_login(self.user)
        data = self.VALID_DATA.copy()
        data["name"] = "RIVER COTTAGE"

        post_response = self.client.post(
            reverse(
                "property:edit_property",
                kwargs={"property_id": property_record.pk},
            ),
            data=data,
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)
        property_record.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertIn("name", response.context["edit_property_form"].errors)
        self.assertContains(
            response,
            'data-modal-auto-open="editPropertyModal"',
        )
        self.assertEqual(property_record.name, "Hill House")

    def test_user_cannot_edit_another_users_property(self):
        property_record = self.create_property(user=self.other_user)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "property:edit_property",
                kwargs={"property_id": property_record.pk},
            ),
            data=self.VALID_DATA,
        )

        self.assertEqual(response.status_code, 404)

    def test_deactivated_property_cannot_be_edited(self):
        property_record = self.create_property(
            state=Property.State.DEACTIVATED,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "property:edit_property",
                kwargs={"property_id": property_record.pk},
            ),
            data=self.VALID_DATA,
        )

        self.assertEqual(response.status_code, 404)

    def test_deactivation_requires_post(self):
        property_record = self.create_property()
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "property:deactivate_property",
                kwargs={"property_id": property_record.pk},
            )
        )
        property_record.refresh_from_db()

        self.assertEqual(response.status_code, 405)
        self.assertEqual(property_record.state, Property.State.ACTIVE)

    def test_deactivation_preserves_property_as_history(self):
        property_record = self.create_property()
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "property:deactivate_property",
                kwargs={"property_id": property_record.pk},
            )
        )
        property_record.refresh_from_db()

        self.assertRedirects(
            response,
            reverse(
                "property:property_detail",
                kwargs={"property_id": property_record.pk},
            ),
        )
        self.assertEqual(property_record.state, Property.State.DEACTIVATED)
        self.assertIsNone(property_record.deleted_at)
        self.assertTrue(Property.objects.filter(pk=property_record.pk).exists())

    def test_user_cannot_deactivate_another_users_property(self):
        property_record = self.create_property(user=self.other_user)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "property:deactivate_property",
                kwargs={"property_id": property_record.pk},
            )
        )
        property_record.refresh_from_db()

        self.assertEqual(response.status_code, 404)
        self.assertEqual(property_record.state, Property.State.ACTIVE)

    def test_reactivation_returns_property_to_active_state(self):
        property_record = self.create_property(
            state=Property.State.DEACTIVATED,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "property:reactivate_property",
                kwargs={"property_id": property_record.pk},
            )
        )
        property_record.refresh_from_db()

        self.assertRedirects(
            response,
            reverse(
                "property:property_detail",
                kwargs={"property_id": property_record.pk},
            ),
        )
        self.assertEqual(property_record.state, Property.State.ACTIVE)

    def test_reactivation_requires_post(self):
        property_record = self.create_property(
            state=Property.State.DEACTIVATED,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "property:reactivate_property",
                kwargs={"property_id": property_record.pk},
            )
        )
        property_record.refresh_from_db()

        self.assertEqual(response.status_code, 405)
        self.assertEqual(property_record.state, Property.State.DEACTIVATED)

    def test_delete_soft_deletes_property_and_redirects_to_list(self):
        property_record = self.create_property()
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "property:delete_property",
                kwargs={"property_id": property_record.pk},
            )
        )
        property_record.refresh_from_db()

        self.assertRedirects(response, reverse("property:properties"))
        self.assertIsNotNone(property_record.deleted_at)
        self.assertTrue(Property.objects.filter(pk=property_record.pk).exists())

    def test_delete_requires_post(self):
        property_record = self.create_property()
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "property:delete_property",
                kwargs={"property_id": property_record.pk},
            )
        )
        property_record.refresh_from_db()

        self.assertEqual(response.status_code, 405)
        self.assertIsNone(property_record.deleted_at)

    def test_user_cannot_delete_another_users_property(self):
        property_record = self.create_property(user=self.other_user)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "property:delete_property",
                kwargs={"property_id": property_record.pk},
            )
        )
        property_record.refresh_from_db()

        self.assertEqual(response.status_code, 404)
        self.assertIsNone(property_record.deleted_at)
