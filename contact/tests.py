from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from note.models import Note

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

    def create_note(
            self,
            user,
            contact,
            content="a note",
    ):
        return Note.objects.create(
            user=user,
            contact=contact,
            content=content,
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

    def test_contact_method_normalises_email_and_rejects_same_contact_duplicate(self):
        contact = self.create_contact(self.user)
        other_contact = self.create_contact(self.user, "Bob")

        method = self.create_method(contact, value=" Alice@Example.COM ")
        same_value_other_contact = self.create_method(
            other_contact,
            value="alice@example.com",
        )

        self.assertEqual(method.value, "alice@example.com")
        self.assertEqual(same_value_other_contact.value, "alice@example.com")

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_method(contact, value="ALICE@example.com")

    def test_hard_deleting_contact_cascades_to_methods(self):
        contact = self.create_contact(self.user)
        self.create_method(contact)

        contact.delete()

        self.assertFalse(ContactMethod.objects.exists())


class ContactFormTests(ContactTestMixin, TestCase):
    def test_contact_form_only_exposes_name_fields(self):
        form = ContactForm()

        self.assertEqual(list(form.fields), ["first_name", "last_name"])

    def test_edit_form_does_not_apply_browser_name_length_limits(self):
        contact = self.create_contact(self.create_user())
        edit_form = ContactForm(instance=contact)
        create_form = ContactCreateForm()

        for name in ("first_name", "last_name"):
            with self.subTest(name=name):
                self.assertNotIn("maxlength", edit_form.fields[name].widget.attrs)
                self.assertEqual(
                    create_form.fields[name].widget.attrs["maxlength"],
                    "150",
                )

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

    def test_contact_method_form_rejects_duplicate_for_same_contact(self):
        contact = self.create_contact(self.create_user())
        self.create_method(contact, value="alice@example.com")

        form = ContactMethodForm(
            data={
                "type": ContactMethod.Type.EMAIL,
                "value": "ALICE@example.com",
            },
            contact=contact,
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(
            list(form.errors["value"]),
            ["This email address is already saved for this contact."],
        )

    def test_contact_method_form_shows_only_duplicate_telephone_error(self):
        contact = self.create_contact(self.create_user())
        self.create_method(
            contact,
            type=ContactMethod.Type.TELEPHONE,
            value="+447700900123",
        )

        form = ContactMethodForm(
            data={"type": ContactMethod.Type.TELEPHONE, "value": "+447700900123"},
            contact=contact,
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(
            list(form.errors["value"]),
            ["This telephone number is already saved for this contact."],
        )

    def test_contact_method_form_prioritises_format_over_duplicate(self):
        contact = self.create_contact(self.create_user())
        self.create_method(
            contact,
            type=ContactMethod.Type.TELEPHONE,
            value="+447700900123",
        )

        form = ContactMethodForm(
            data={"type": ContactMethod.Type.EMAIL, "value": "+447700900123"},
            contact=contact,
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(list(form.errors["value"]), ["Enter a valid email address."])


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

    def test_contacts_for_user_summarises_first_email_and_telephone(self):
        contact = self.create_contact(self.user)
        self.create_method(contact, value="first@example.com")
        self.create_method(contact, value="second@example.com")
        self.create_method(
            contact,
            type=ContactMethod.Type.TELEPHONE,
            value="+447700900001",
        )
        self.create_method(
            contact,
            type=ContactMethod.Type.TELEPHONE,
            value="+447700900002",
        )

        summary = contacts_for_user(user=self.user).get(pk=contact.pk)

        self.assertEqual(summary.first_email, "first@example.com")
        self.assertEqual(summary.first_telephone, "+447700900001")

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

    def test_confirmation_dialogs_keep_long_contact_values_out_of_titles(self):
        long_name = "A" * 80
        contact = self.create_contact(self.user, first_name=long_name)
        long_email = f"contact{'2' * 85}@example.com"
        self.create_method(contact, value=long_email)

        response = self.client.get(reverse("contact:contacts"))

        self.assertContains(response, 'id="editContactModalLabel">Edit contact</h2>')
        self.assertContains(response, 'id="deleteContactModalLabel">Delete contact?</h2>')
        self.assertContains(response, 'class="modal-context-value">' + long_name)
        self.assertContains(response, 'class="modal-context-value">' + long_email)
        self.assertContains(response, 'class="btn btn-danger" type="submit">Delete contact')
        self.assertContains(response, 'class="btn btn-danger" type="submit">Delete detail')

    def test_contact_details_group_email_and_telephone_methods(self):
        contact = self.create_contact(self.user)
        email = self.create_method(contact, value="alice@example.com")
        telephone = self.create_method(
            contact,
            type=ContactMethod.Type.TELEPHONE,
            value="+447700900123",
        )

        response = self.client.get(reverse("contact:contacts"))

        self.assertEqual(response.context["email_methods"], [email])
        self.assertEqual(response.context["telephone_methods"], [telephone])
        self.assertContains(response, 'id="contact-emails-heading"')
        self.assertContains(response, 'id="contact-telephones-heading"')
        self.assertContains(response, 'class="contact-method-list"', count=2)
        self.assertContains(response, 'aria-label="Edit email alice@example.com"')
        self.assertContains(response, 'aria-label="Delete telephone +447700900123"')
        details_html = response.content.decode().split('id="contact-emails-heading"', 1)[1]
        email_html, telephone_html = details_html.split('id="contact-telephones-heading"', 1)
        self.assertIn("alice@example.com", email_html)
        self.assertNotIn("+447700900123", email_html)
        self.assertIn("+447700900123", telephone_html)

    def test_long_email_keeps_full_value_in_link_and_label(self):
        contact = self.create_contact(self.user)
        email = f"contact72{'2' * 90}@example.com"
        self.create_method(contact, value=email)

        response = self.client.get(reverse("contact:contacts"))

        self.assertContains(response, 'contact-method-value--email')
        self.assertContains(response, f'href="mailto:{email}"')
        self.assertContains(response, f'title="{email}"')
        self.assertContains(response, f'aria-label="Email {email}"')

    def test_contact_list_shows_first_email_and_telephone_only(self):
        contact = self.create_contact(self.user)
        for value in ("first@example.com", "second@example.com"):
            self.create_method(contact, value=value)
        for value in ("+447700900001", "+447700900002"):
            self.create_method(
                contact,
                type=ContactMethod.Type.TELEPHONE,
                value=value,
            )

        response = self.client.get(reverse("contact:contacts"))
        list_html = response.content.decode().split('class="contact-command-list', 1)[1]
        list_html = list_html.split('class="contact-detail-column', 1)[0]

        self.assertIn("first@example.com", list_html)
        self.assertIn("+447700900001", list_html)
        self.assertNotIn("second@example.com", list_html)
        self.assertNotIn("+447700900002", list_html)
        self.assertContains(response, "second@example.com")
        self.assertContains(response, "+447700900002")

    def test_deactivated_contact_list_shows_state_instead_of_methods(self):
        contact = self.create_contact(
            self.user,
            state=Contact.State.DEACTIVATED,
        )
        self.create_method(contact, value="alice@example.com")

        response = self.client.get(
            reverse("contact:contacts"),
            {"state": Contact.State.DEACTIVATED},
        )
        list_html = response.content.decode().split('class="contact-command-list', 1)[1]
        list_html = list_html.split('class="contact-detail-column', 1)[0]

        self.assertIn("Deactivated", list_html)
        self.assertNotIn("alice@example.com", list_html)
        self.assertContains(response, "alice@example.com")
        self.assertNotContains(response, 'class="contact-method-actions"')

    def test_contact_list_defaults_to_active_and_can_show_deactivated(self):
        active = self.create_contact(self.user, "Active")
        deactivated = self.create_contact(
            self.user,
            "Deactivated",
            state=Contact.State.DEACTIVATED,
        )

        for query, expected in (
            ({}, [active]),
            ({"state": Contact.State.DEACTIVATED}, [deactivated]),
            ({"state": "all"}, [active, deactivated]),
        ):
            with self.subTest(query=query):
                response = self.client.get(reverse("contact:contacts"), query)
                self.assertCountEqual(response.context["page_obj"].object_list, expected)

    def test_deactivated_only_contact_list_offers_all_states(self):
        self.create_contact(self.user, state=Contact.State.DEACTIVATED)

        response = self.client.get(reverse("contact:contacts"))

        self.assertContains(response, "No active contacts")
        self.assertContains(response, "Show all states")

    def test_contacts_view_paginates_twenty_at_a_time(self):
        for number in range(21):
            self.create_contact(self.user, f"Contact {number:02}")

        first_page = self.client.get(reverse("contact:contacts"))
        second_page = self.client.get(reverse("contact:contacts"), {"page": 2})

        self.assertEqual(len(first_page.context["page_obj"]), 20)
        self.assertEqual(len(second_page.context["page_obj"]), 1)
        self.assertContains(first_page, "Page 1 of 2")
        self.assertContains(second_page, "Page 2 of 2")
        self.assertContains(second_page, 'aria-disabled="true">Next →</span>')

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
        post_response = self.client.post(
            reverse("contact:add_contact"),
            {"first_name": "Alice", "email": "invalid"},
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

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

    def test_invalid_edit_contact_redirects_and_restores_bound_form_once(self):
        contact = self.create_contact(self.user, last_name="Smith")

        post_response = self.client.post(
            reverse("contact:edit_contact", args=[contact.pk]),
            {"first_name": "", "last_name": "Changed"},
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn(reverse("contact:contacts"), post_response.url)
        self.assertIn(f"selected={contact.pk}", post_response.url)
        self.assertIn("form_state=", post_response.url)
        self.assertNotIn("first_name", post_response.url)

        response = self.client.get(post_response.url)
        form = response.context["edit_contact_form"]
        contact.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_contact"], contact)
        self.assertEqual(response.context["active_tab"], "details")
        self.assertEqual(response.context["open_modal"], "editContactModal")
        self.assertTrue(form.is_bound)
        self.assertEqual(form["first_name"].value(), "")
        self.assertEqual(form["last_name"].value(), "Changed")
        self.assertIn("first_name", form.errors)
        self.assertEqual(contact.first_name, "Alice")
        self.assertEqual(contact.last_name, "Smith")

        refreshed_response = self.client.get(post_response.url)
        self.assertFalse(refreshed_response.context["edit_contact_form"].is_bound)
        self.assertIsNone(refreshed_response.context["open_modal"])

    def test_overlong_edit_contact_name_is_rejected_with_visible_error(self):
        contact = self.create_contact(self.user)
        overlong_name = "a" * 151

        post_response = self.client.post(
            reverse("contact:edit_contact", args=[contact.pk]),
            {"first_name": overlong_name, "last_name": ""},
        )
        response = self.client.get(post_response.url)
        contact.refresh_from_db()

        self.assertEqual(post_response.status_code, 302)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["edit_contact_form"]["first_name"].value(),
            overlong_name,
        )
        self.assertIn("first_name", response.context["edit_contact_form"].errors)
        self.assertEqual(contact.first_name, "Alice")

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

    def test_duplicate_contact_method_reopens_add_modal(self):
        contact = self.create_contact(self.user)
        self.create_method(contact, value="alice@example.com")

        post_response = self.client.post(
            reverse("contact:add_contact_method", args=[contact.pk]),
            {"type": ContactMethod.Type.EMAIL, "value": "ALICE@example.com"},
        )
        response = self.client.get(post_response.url)

        self.assertEqual(contact.contact_methods.count(), 1)
        self.assertEqual(response.context["open_modal"], "addContactMethodModal")
        self.assertIn("value", response.context["add_contact_method_form"].errors)

    def test_edit_method_query_opens_modal_with_method_form(self):
        contact = self.create_contact(self.user)
        method = self.create_method(contact)

        response = self.client.get(
            reverse("contact:contacts"),
            {"selected": contact.pk, "edit_method": method.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_contact"], contact)
        self.assertEqual(response.context["edit_contact_method"], method)
        self.assertEqual(
            response.context["edit_contact_method_form"].instance,
            method,
        )
        self.assertEqual(response.context["open_modal"], "editContactMethodModal")
        self.assertContains(
            response,
            'data-modal-clear-query="edit_method form_state"',
        )
        self.assertContains(
            response,
            'data-modal-auto-open="editContactMethodModal"',
        )

    def test_invalid_method_form_reopens_correct_modal(self):
        contact = self.create_contact(self.user)

        post_response = self.client.post(
            reverse("contact:add_contact_method", args=[contact.pk]),
            {"type": ContactMethod.Type.EMAIL, "value": "invalid"},
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn(f"selected={contact.pk}", post_response.url)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["open_modal"], "addContactMethodModal")
        self.assertIn(
            "value",
            response.context["add_contact_method_form"].errors,
        )

    def test_invalid_edit_method_form_reopens_correct_modal(self):
        contact = self.create_contact(self.user)
        method = self.create_method(contact)

        post_response = self.client.post(
            reverse(
                "contact:edit_contact_method",
                args=[contact.pk, method.pk],
            ),
            {"type": ContactMethod.Type.EMAIL, "value": "invalid"},
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn(f"selected={contact.pk}", post_response.url)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)
        form = response.context["edit_contact_method_form"]
        method.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["open_modal"], "editContactMethodModal")
        self.assertEqual(response.context["edit_contact_method"], method)
        self.assertEqual(form["value"].value(), "invalid")
        self.assertIn("value", form.errors)
        self.assertEqual(method.value, "alice@example.com")

    def test_cross_user_contact_and_method_mutations_return_404(self):
        contact = self.create_contact(self.other_user, "Bob")
        method = self.create_method(contact, value="bob@example.com")
        note = self.create_note(self.other_user, contact)
        contact_urls = (
            reverse("contact:edit_contact", args=[contact.pk]),
            reverse("contact:deactivate_contact", args=[contact.pk]),
            reverse("contact:reactivate_contact", args=[contact.pk]),
            reverse("contact:delete_contact", args=[contact.pk]),
            reverse("contact:add_contact_method", args=[contact.pk]),
            reverse("contact:edit_contact_method", args=[contact.pk, method.pk]),
            reverse("contact:delete_contact_method", args=[contact.pk, method.pk]),
            reverse("contact:add_contact_note", args=[contact.pk]),
            reverse("contact:edit_contact_note", args=[contact.pk, note.pk]),
            reverse("contact:delete_contact_note", args=[contact.pk, note.pk]),
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
        self.assertEqual(
            self.client.post(
                reverse("contact:add_contact_note", args=[contact.pk]),
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
        note = self.create_note(self.user, contact)
        urls = (
            reverse("contact:add_contact"),
            reverse("contact:edit_contact", args=[contact.pk]),
            reverse("contact:deactivate_contact", args=[contact.pk]),
            reverse("contact:reactivate_contact", args=[contact.pk]),
            reverse("contact:delete_contact", args=[contact.pk]),
            reverse("contact:add_contact_method", args=[contact.pk]),
            reverse("contact:edit_contact_method", args=[contact.pk, method.pk]),
            reverse("contact:delete_contact_method", args=[contact.pk, method.pk]),
            reverse("contact:add_contact_note", args=[contact.pk]),
            reverse("contact:edit_contact_note", args=[contact.pk, note.pk]),
            reverse("contact:delete_contact_note", args=[contact.pk, note.pk]),
        )

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)

    def test_add_edit_and_delete_contact_note_works_and_redirects_back_to_selected_contacts_notes_tab(self):
        contact = self.create_contact(self.user)

        expected_url = (
            f"{reverse('contact:contacts')}"
            f"?selected={contact.pk}&tab=notes"
        )

        add_response = self.client.post(
            reverse("contact:add_contact_note", args=[contact.pk]), {"content": "note"})
        note = contact.notes.get()
        self.assertRedirects(add_response, expected_url)

        edit_content = "edit"
        edit_response = self.client.post(
            reverse(
                "contact:edit_contact_note",
                args=[contact.pk, note.pk]),
                {"content": edit_content},)
        note.refresh_from_db()
        self.assertRedirects(edit_response, expected_url)
        self.assertEqual(note.content, edit_content)

        delete_response = self.client.post(
            reverse(
                "contact:delete_contact_note",
                args=[contact.pk, note.pk],
            )
        )
        self.assertRedirects(delete_response, expected_url)
        self.assertFalse(Note.objects.filter(pk=note.pk).exists())

    def test_note_from_different_owned_contact_cannot_be_mutated(self):
        contact = self.create_contact(self.user)
        other_contact = self.create_contact(self.user, "Other")
        note = self.create_note(self.user, other_contact)

        for route in ("edit_contact_note", "delete_contact_note"):
            with self.subTest(route=route):
                response = self.client.post(
                    reverse(f"contact:{route}", args=[contact.pk, note.pk])
                )
                self.assertEqual(response.status_code, 404)

    def test_invalid_add_note_form_returns_errors(self):
        contact = self.create_contact(self.user)

        post_response = self.client.post(
            reverse("contact:add_contact_note", args=[contact.pk]),
            {"content": ""},
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn(f"selected={contact.pk}", post_response.url)
        self.assertIn("tab=notes", post_response.url)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_tab"], "notes")
        self.assertEqual(response.context["selected_contact"], contact)
        form = response.context["add_contact_note_form"]
        self.assertEqual(form["content"].value(), "")
        self.assertIn(
            "content",
            response.context["add_contact_note_form"].errors,
        )
        self.assertEqual(Note.objects.filter(user=self.user).count(), 0)

    def test_invalid_edit_note_form_returns_errors(self):
        contact = self.create_contact(self.user)
        note = self.create_note(self.user, contact)
        original_content = note.content

        post_response = self.client.post(
            reverse("contact:edit_contact_note", args=[contact.pk, note.pk]),
            {"content": ""},
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn(reverse("contact:contacts"), post_response.url)
        self.assertIn(f"selected={contact.pk}", post_response.url)
        self.assertIn("tab=notes", post_response.url)
        self.assertIn("form_state=", post_response.url)
        self.assertNotIn("content", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_tab"], "notes")
        self.assertEqual(response.context["selected_contact"], contact)
        self.assertEqual(response.context["edit_contact_note"], note)
        form = response.context["edit_contact_note_form"]
        note.refresh_from_db()

        self.assertEqual(note.content, original_content)
        self.assertEqual(form["content"].value(), "")
        self.assertIn("content", form.errors)

        refreshed_response = self.client.get(post_response.url)
        self.assertIsNone(refreshed_response.context["edit_contact_note_form"])

    def test_contacts_notes_tab_renders_owned_notes_in_correct_order(self):
        contact = self.create_contact(self.user)
        data = [["newest", 0], ["middle", 1], ["oldest", 2]]

        for content, days in data:
            note = self.create_note(self.user, contact, content)
            note.created_at = timezone.now() - timedelta(days=days)
            note.save(update_fields=["created_at"])

        response = self.client.get(reverse("contact:contacts"), {"tab": "notes"})
        self.assertEqual(response.status_code, 200)
        notes = response.context["notes"]

        for i, note in enumerate(notes):
            self.assertEqual(note.content, data[i][0])

    def test_contacts_notes_tab_is_contact_and_user_scoped(self):
        contact1 = self.create_contact(self.user)
        contact2 = self.create_contact(self.user)
        note1 = self.create_note(self.user, contact1)
        self.create_note(self.user, contact2)
        self.create_note(self.other_user, self.create_contact(self.other_user))

        response = self.client.get(reverse("contact:contacts"), {"tab": "notes", "selected": contact1.pk})
        self.assertEqual(list(response.context["notes"]), [note1])
