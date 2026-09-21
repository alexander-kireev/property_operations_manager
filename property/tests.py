from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

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
