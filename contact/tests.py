from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

from .forms import ContactCreateForm, ContactForm, ContactMethodForm
from .models import Contact, ContactMethod
from .selectors import (
    contact_methods_for_contact,
    contacts_for_user,
    filtered_contacts_for_user,
)
from .services import (
    create_contact,
    create_contact_method,
    deactivate_contact,
    delete_contact,
    delete_contact_method,
    reactivate_contact,
    update_contact,
    update_contact_method,
)


class ContactTestMixin:
    TEST_PASSWORD = "HolidayHome123!"

    def create_user(self, email="alice@example.com"):
        return User.objects.create_user(
            email=email,
            first_name="Test",
            last_name="User",
            password=self.TEST_PASSWORD,
        )

    def create_contact(self, user, first_name="Alice", **values):
        return Contact.objects.create(
            user=user,
            first_name=first_name,
            **values,
        )

    def create_method(
        self,
        contact,
        type=ContactMethod.Type.EMAIL,
        value="alice@example.com",
    ):
        return ContactMethod.objects.create(
            contact=contact,
            type=type,
            value=value,
        )


class ContactModelTests(ContactTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()

    def test_contact_defaults_and_string_value(self):
        contact = self.create_contact(self.user, last_name="Smith")

        self.assertEqual(contact.state, Contact.State.ACTIVE)
        self.assertIsNone(contact.deleted_at)
        self.assertEqual(str(contact), "Alice Smith")

    def test_contact_string_value_handles_missing_last_name(self):
        contact = self.create_contact(self.user)

        self.assertEqual(str(contact), "Alice")

    def test_contact_method_validates_value_for_its_type(self):
        contact = self.create_contact(self.user)
        valid_email = ContactMethod(
            contact=contact,
            type=ContactMethod.Type.EMAIL,
            value="person@example.com",
        )
        valid_phone = ContactMethod(
            contact=contact,
            type=ContactMethod.Type.TELEPHONE,
            value="+447700900123",
        )

        valid_email.full_clean()
        valid_phone.full_clean()

        for type, value in (
            (ContactMethod.Type.EMAIL, "not-an-email"),
            (ContactMethod.Type.TELEPHONE, "07700 900123"),
        ):
            with self.subTest(type=type):
                method = ContactMethod(contact=contact, type=type, value=value)
                with self.assertRaises(ValidationError):
                    method.full_clean()

    def test_hard_deleting_contact_cascades_to_methods(self):
        contact = self.create_contact(self.user)
        self.create_method(contact)

        contact.delete()

        self.assertFalse(ContactMethod.objects.exists())


class ContactFormTests(ContactTestMixin, TestCase):
    def test_contact_form_only_exposes_name_fields(self):
        form = ContactForm()

        self.assertEqual(list(form.fields), ["first_name", "last_name"])

    def test_create_form_accepts_optional_initial_methods(self):
        form = ContactCreateForm(
            data={
                "first_name": "Alice",
                "last_name": "Smith",
                "email": "alice@example.com",
                "telephone": "+447700900123",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_create_form_allows_contact_without_methods(self):
        form = ContactCreateForm(data={"first_name": "Alice"})

        self.assertTrue(form.is_valid(), form.errors)

    def test_create_form_rejects_invalid_initial_methods(self):
        form = ContactCreateForm(
            data={
                "first_name": "Alice",
                "email": "invalid",
                "telephone": "07700 900123",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)
        self.assertIn("telephone", form.errors)

    def test_contact_method_form_applies_type_specific_validation(self):
        email_form = ContactMethodForm(
            data={"type": ContactMethod.Type.EMAIL, "value": "invalid"}
        )
        phone_form = ContactMethodForm(
            data={"type": ContactMethod.Type.TELEPHONE, "value": "+441234567890"}
        )

        self.assertFalse(email_form.is_valid())
        self.assertIn("value", email_form.errors)
        self.assertTrue(phone_form.is_valid(), phone_form.errors)


class ContactSelectorTests(ContactTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.other_user = self.create_user("bob@example.com")

    def test_contacts_for_user_scopes_owner_and_soft_deletion(self):
        visible = self.create_contact(self.user)
        self.create_contact(self.other_user, "Bob")
        self.create_contact(self.user, "Deleted", deleted_at=timezone.now())

        self.assertEqual(list(contacts_for_user(user=self.user)), [visible])

    def test_contacts_for_user_prefetches_methods(self):
        contact = self.create_contact(self.user)
        method = self.create_method(contact)

        with self.assertNumQueries(2):
            contacts = list(contacts_for_user(user=self.user))
            self.assertEqual(list(contacts[0].contact_methods.all()), [method])

    def test_search_matches_names_and_contact_method_values(self):
        first_name_match = self.create_contact(self.user, "Alex")
        last_name_match = self.create_contact(
            self.user,
            "Morgan",
            last_name="Alexander",
        )
        email_match = self.create_contact(self.user, "Email")
        phone_match = self.create_contact(self.user, "Phone")
        self.create_method(email_match, value="alex@example.com")
        self.create_method(
            phone_match,
            type=ContactMethod.Type.TELEPHONE,
            value="+441234567890",
        )

        result = filtered_contacts_for_user(user=self.user, search="alex")
        self.assertEqual(
            set(result),
            {first_name_match, last_name_match, email_match},
        )
        self.assertEqual(
            list(filtered_contacts_for_user(user=self.user, search="123456")),
            [phone_match],
        )

    def test_search_returns_each_contact_once(self):
        contact = self.create_contact(self.user, "Alice")
        self.create_method(contact, value="alice@example.com")
        self.create_method(
            contact,
            type=ContactMethod.Type.TELEPHONE,
            value="+441111111111",
        )

        self.assertEqual(
            list(filtered_contacts_for_user(user=self.user, search="Alice")),
            [contact],
        )

    def test_state_filter_and_supported_sort_options(self):
        alpha = self.create_contact(self.user, "Alpha")
        zebra = self.create_contact(
            self.user,
            "Zebra",
            state=Contact.State.DEACTIVATED,
        )
        earlier = timezone.now() - timedelta(days=2)
        later = timezone.now() - timedelta(days=1)
        Contact.objects.filter(pk=alpha.pk).update(created_at=earlier)
        Contact.objects.filter(pk=zebra.pk).update(created_at=later)

        self.assertEqual(
            list(
                filtered_contacts_for_user(
                    user=self.user,
                    state=Contact.State.DEACTIVATED,
                )
            ),
            [zebra],
        )

        expected = {
            "name": [alpha, zebra],
            "-name": [zebra, alpha],
            "created_at": [alpha, zebra],
            "-created_at": [zebra, alpha],
        }
        for sort, contacts in expected.items():
            with self.subTest(sort=sort):
                self.assertEqual(
                    list(filtered_contacts_for_user(user=self.user, sort=sort)),
                    contacts,
                )

    def test_contact_methods_for_contact_only_returns_its_methods(self):
        contact = self.create_contact(self.user)
        other_contact = self.create_contact(self.user, "Other")
        wanted = self.create_method(contact)
        self.create_method(other_contact, value="other@example.com")

        self.assertEqual(
            list(contact_methods_for_contact(contact=contact)),
            [wanted],
        )


class ContactServiceTests(ContactTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()

    def test_create_contact_persists_initial_methods(self):
        contact = create_contact(
            user=self.user,
            first_name="Alice",
            last_name="Smith",
            email="alice@example.com",
            telephone="+447700900123",
        )

        self.assertEqual(contact.user, self.user)
        self.assertEqual(contact.contact_methods.count(), 2)
        self.assertSetEqual(
            set(contact.contact_methods.values_list("type", "value")),
            {
                (ContactMethod.Type.EMAIL, "alice@example.com"),
                (ContactMethod.Type.TELEPHONE, "+447700900123"),
            },
        )

    def test_create_contact_allows_no_initial_methods(self):
        contact = create_contact(user=self.user, first_name="Alice")

        self.assertFalse(contact.contact_methods.exists())

    def test_update_contact_preserves_owner_and_lifecycle(self):
        contact = self.create_contact(self.user)

        update_contact(contact=contact, first_name="Alicia", last_name="Jones")
        contact.refresh_from_db()

        self.assertEqual(str(contact), "Alicia Jones")
        self.assertEqual(contact.user, self.user)
        self.assertEqual(contact.state, Contact.State.ACTIVE)

    def test_contact_lifecycle_services_are_idempotent(self):
        contact = self.create_contact(self.user)

        deactivate_contact(contact=contact)
        deactivate_contact(contact=contact)
        self.assertEqual(contact.state, Contact.State.DEACTIVATED)

        reactivate_contact(contact=contact)
        reactivate_contact(contact=contact)
        self.assertEqual(contact.state, Contact.State.ACTIVE)

        delete_contact(contact=contact)
        original_deleted_at = contact.deleted_at
        delete_contact(contact=contact)
        self.assertEqual(contact.deleted_at, original_deleted_at)

    def test_contact_method_services_create_update_and_delete(self):
        contact = self.create_contact(self.user)
        method = create_contact_method(
            contact=contact,
            type=ContactMethod.Type.EMAIL,
            value="alice@example.com",
        )

        update_contact_method(
            contact_method=method,
            type=ContactMethod.Type.TELEPHONE,
            value="+447700900123",
        )
        method.refresh_from_db()
        self.assertEqual(method.type, ContactMethod.Type.TELEPHONE)

        delete_contact_method(contact_method=method)
        self.assertFalse(ContactMethod.objects.filter(pk=method.pk).exists())


class ContactViewTests(ContactTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.other_user = self.create_user("bob@example.com")
        self.client.force_login(self.user)

    def test_contacts_view_requires_login(self):
        self.client.logout()

        response = self.client.get(reverse("contact:contacts"))

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('contact:contacts')}",
        )

    def test_contacts_view_renders_owned_contacts_and_methods(self):
        contact = self.create_contact(self.user)
        method = self.create_method(contact)
        other_contact = self.create_contact(self.other_user, "Bob")

        response = self.client.get(reverse("contact:contacts"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(contact))
        self.assertContains(response, method.value)
        self.assertNotContains(response, str(other_contact))
        self.assertEqual(response.context["selected_contact"], contact)

    def test_contacts_view_paginates_twenty_at_a_time(self):
        for number in range(21):
            self.create_contact(self.user, f"Contact {number:02}")

        first_page = self.client.get(reverse("contact:contacts"))
        second_page = self.client.get(reverse("contact:contacts"), {"page": 2})

        self.assertEqual(len(first_page.context["page_obj"]), 20)
        self.assertEqual(len(second_page.context["page_obj"]), 1)

    def test_contacts_view_normalises_list_parameters(self):
        self.create_contact(self.user)

        response = self.client.get(
            reverse("contact:contacts"),
            {"search": " Alice ", "state": "invalid", "sort": "invalid"},
        )

        self.assertEqual(response.context["search"], "Alice")
        self.assertEqual(response.context["state"], "")
        self.assertEqual(response.context["sort"], "name")
        self.assertEqual(response.context["list_query"], "search=Alice")

    def test_contacts_view_normalises_workspace_tab(self):
        contact = self.create_contact(self.user)

        notes_response = self.client.get(
            reverse("contact:contacts"),
            {"selected": contact.pk, "tab": "notes"},
        )
        invalid_response = self.client.get(
            reverse("contact:contacts"),
            {"selected": contact.pk, "tab": "invalid"},
        )

        self.assertEqual(notes_response.context["active_tab"], "notes")
        self.assertContains(notes_response, 'class="notes-board-shell"')
        self.assertEqual(invalid_response.context["active_tab"], "details")

    def test_add_contact_creates_contact_and_initial_methods(self):
        response = self.client.post(
            reverse("contact:add_contact"),
            {
                "first_name": "Alice",
                "last_name": "Smith",
                "email": "alice@example.com",
                "telephone": "+447700900123",
            },
        )
        contact = Contact.objects.get(first_name="Alice")

        self.assertEqual(contact.user, self.user)
        self.assertEqual(contact.contact_methods.count(), 2)
        self.assertRedirects(
            response,
            f"{reverse('contact:contacts')}?selected={contact.pk}",
        )

    def test_invalid_add_contact_reopens_modal_without_partial_creation(self):
        response = self.client.post(
            reverse("contact:add_contact"),
            {"first_name": "Alice", "email": "invalid"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["open_modal"], "addContactModal")
        self.assertIn("email", response.context["add_contact_form"].errors)
        self.assertFalse(Contact.objects.exists())

    def test_edit_contact_updates_active_owned_contact(self):
        contact = self.create_contact(self.user)

        response = self.client.post(
            reverse("contact:edit_contact", args=[contact.pk]),
            {"first_name": "Alicia", "last_name": "Jones"},
        )
        contact.refresh_from_db()

        self.assertEqual(str(contact), "Alicia Jones")
        self.assertRedirects(
            response,
            f"{reverse('contact:contacts')}?selected={contact.pk}",
        )

    def test_lifecycle_views_change_state_and_soft_delete(self):
        contact = self.create_contact(self.user)

        self.client.post(reverse("contact:deactivate_contact", args=[contact.pk]))
        contact.refresh_from_db()
        self.assertEqual(contact.state, Contact.State.DEACTIVATED)

        self.client.post(reverse("contact:reactivate_contact", args=[contact.pk]))
        contact.refresh_from_db()
        self.assertEqual(contact.state, Contact.State.ACTIVE)

        self.client.post(reverse("contact:delete_contact", args=[contact.pk]))
        contact.refresh_from_db()
        self.assertIsNotNone(contact.deleted_at)
        self.assertTrue(Contact.objects.filter(pk=contact.pk).exists())

    def test_add_edit_and_delete_contact_method(self):
        contact = self.create_contact(self.user)

        add_response = self.client.post(
            reverse("contact:add_contact_method", args=[contact.pk]),
            {"type": ContactMethod.Type.EMAIL, "value": "alice@example.com"},
        )
        method = contact.contact_methods.get()
        self.assertEqual(add_response.status_code, 302)

        edit_response = self.client.post(
            reverse(
                "contact:edit_contact_method",
                args=[contact.pk, method.pk],
            ),
            {
                "type": ContactMethod.Type.TELEPHONE,
                "value": "+447700900123",
            },
        )
        method.refresh_from_db()
        self.assertEqual(edit_response.status_code, 302)
        self.assertEqual(method.type, ContactMethod.Type.TELEPHONE)

        delete_response = self.client.post(
            reverse(
                "contact:delete_contact_method",
                args=[contact.pk, method.pk],
            )
        )
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(ContactMethod.objects.filter(pk=method.pk).exists())

    def test_invalid_method_form_reopens_correct_modal(self):
        contact = self.create_contact(self.user)

        response = self.client.post(
            reverse("contact:add_contact_method", args=[contact.pk]),
            {"type": ContactMethod.Type.EMAIL, "value": "invalid"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["open_modal"], "addContactMethodModal")
        self.assertIn(
            "value",
            response.context["add_contact_method_form"].errors,
        )

    def test_cross_user_contact_and_method_mutations_return_404(self):
        contact = self.create_contact(self.other_user, "Bob")
        method = self.create_method(contact, value="bob@example.com")
        contact_urls = (
            reverse("contact:edit_contact", args=[contact.pk]),
            reverse("contact:deactivate_contact", args=[contact.pk]),
            reverse("contact:reactivate_contact", args=[contact.pk]),
            reverse("contact:delete_contact", args=[contact.pk]),
            reverse("contact:add_contact_method", args=[contact.pk]),
            reverse(
                "contact:edit_contact_method",
                args=[contact.pk, method.pk],
            ),
            reverse(
                "contact:delete_contact_method",
                args=[contact.pk, method.pk],
            ),
        )

        for url in contact_urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, {}).status_code, 404)

    def test_method_from_different_owned_contact_cannot_be_mutated(self):
        contact = self.create_contact(self.user)
        other_contact = self.create_contact(self.user, "Other")
        method = self.create_method(other_contact)

        for route in ("edit_contact_method", "delete_contact_method"):
            with self.subTest(route=route):
                response = self.client.post(
                    reverse(f"contact:{route}", args=[contact.pk, method.pk]),
                    {"type": ContactMethod.Type.EMAIL, "value": "new@example.com"},
                )
                self.assertEqual(response.status_code, 404)

    def test_deactivated_contact_is_read_only(self):
        contact = self.create_contact(
            self.user,
            state=Contact.State.DEACTIVATED,
        )

        self.assertEqual(
            self.client.post(
                reverse("contact:edit_contact", args=[contact.pk]),
                {"first_name": "Changed"},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("contact:add_contact_method", args=[contact.pk]),
                {"type": ContactMethod.Type.EMAIL, "value": "a@example.com"},
            ).status_code,
            404,
        )

    def test_soft_deleted_contact_is_not_selectable_or_mutable(self):
        contact = self.create_contact(
            self.user,
            deleted_at=timezone.now(),
        )

        list_response = self.client.get(
            reverse("contact:contacts"),
            {"selected": contact.pk},
        )
        edit_response = self.client.post(
            reverse("contact:edit_contact", args=[contact.pk]),
            {"first_name": "Changed"},
        )

        self.assertIsNone(list_response.context["selected_contact"])
        self.assertEqual(edit_response.status_code, 404)

    def test_mutation_views_reject_get_requests(self):
        contact = self.create_contact(self.user)
        method = self.create_method(contact)
        urls = (
            reverse("contact:add_contact"),
            reverse("contact:edit_contact", args=[contact.pk]),
            reverse("contact:deactivate_contact", args=[contact.pk]),
            reverse("contact:reactivate_contact", args=[contact.pk]),
            reverse("contact:delete_contact", args=[contact.pk]),
            reverse("contact:add_contact_method", args=[contact.pk]),
            reverse("contact:edit_contact_method", args=[contact.pk, method.pk]),
            reverse("contact:delete_contact_method", args=[contact.pk, method.pk]),
        )

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)
