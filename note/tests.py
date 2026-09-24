from django.test import TestCase

from contact.models import Contact
from accounts.models import User
from note.models import Note
from note.forms import NoteForm

from note.selectors import (
    notes_for_contact,
    general_notes_for_user,
)

from note.services import (
    create_note,
    update_note,
    delete_note,
)


class NoteTestMixin:
    password = "HolidayHome123!"
    general_content = "general note"
    contact_content = "contact note"

    def create_user(self, email="alice@example.com"):
        return User.objects.create_user(
            email=email,
            first_name="Alice",
            last_name="Smith",
            password=self.password,
        )

    def create_contact(self, user, first_name="Alex", **values):
        return Contact.objects.create(user=user, first_name=first_name, **values)

    def create_general_note(self, user, content="general note"):
        return Note.objects.create(user=user, content=content)

    def create_contact_note(self, user, contact, content="contact note"):
        return Note.objects.create(user=user, contact=contact, content=content)

    def valid_general_data(self):
        return {
            "content": self.general_content,
        }

    def valid_contact_data(self):
        return {
            "content": self.contact_content,
        }

class NoteModelTests(NoteTestMixin, TestCase):
    def test_can_create_general_note_with_user_ownership(self):   
        user = self.create_user()
        general_note = self.create_general_note(user=user)
       
        self.assertEqual(general_note.user, user)

    def test_can_create_contact_note_with_user_onwership_scoped_to_contact(self):
        user = self.create_user()
        contact = self.create_contact(user=user)
        contact_note = self.create_contact_note(user=user, contact=contact)

        self.assertEqual(contact_note.user, user)
        self.assertEqual(contact_note.contact, contact)
    

class NoteFormTests(NoteTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.contact = self.create_contact(user=self.user)

    def test_valid_data_exposes_only_editable_fields(self):
        form = NoteForm(data=self.valid_general_data())

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            list(form.fields),
            ["content",]
        )

    def test_form_rejects_empty_content(self):
        form = NoteForm(data={"content": ""})

        self.assertFalse(form.is_valid())
        self.assertIn("content", form.errors)

    def test_content_limit_is_250_characters(self):
        self.assertTrue(NoteForm(data={"content": "n" * 250}).is_valid())
        form = NoteForm(data={"content": "n" * 251})
        self.assertFalse(form.is_valid())
        self.assertIn("content", form.errors)


class NoteSelectorTests(NoteTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.other_user = self.create_user("bob@example.com")
        self.contact = self.create_contact(user=self.user)

    def test_general_notes_are_scoped_to_user(self):
        user1_note = self.create_general_note(user=self.user)
        self.create_contact_note(user=self.user, contact=self.contact)
        self.create_general_note(user=self.other_user)
        
        self.assertEqual(list(general_notes_for_user(user=self.user)), [user1_note])

    def test_contact_notes_are_scoped_to_user_and_contact(self):
        user1_note = self.create_contact_note(
            user=self.user,
            contact=self.contact,
        )

        identical_contact = self.create_contact(user=self.user)
        self.create_contact_note(
            user=self.user,
            contact=identical_contact,
        )

        self.create_contact_note(
            user=self.other_user,
            contact=self.contact,
        )

        self.assertEqual(list(notes_for_contact(user=self.user, contact=self.contact)), [user1_note])


class NoteServiceTests(NoteTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.contact = self.create_contact(user=self.user)

    def test_can_create_general_note(self):
        note = create_note(user=self.user, content=self.general_content)

        self.assertEqual(note.user, self.user)
        self.assertEqual(note.content, self.general_content)
        self.assertEqual(note.contact, None)

    def test_can_create_contact_note(self):
        note = create_note(
            user=self.user,
            content=self.general_content,
            contact=self.contact,)

        self.assertEqual(note.user, self.user)
        self.assertEqual(note.content, self.general_content)
        self.assertEqual(note.contact, self.contact)

    def test_can_update_general_note_content(self):
        updated_content = "updated"
        note = self.create_general_note(user=self.user)
        note = update_note(note=note, content=updated_content)

        note.refresh_from_db()

        self.assertEqual(note.user, self.user)
        self.assertEqual(note.contact, None)
        self.assertEqual(note.content, updated_content)

    def test_can_update_contact_note_content(self):
        updated_content = "updated"
        note = self.create_contact_note(user=self.user, contact=self.contact,)
        note = update_note(note=note, content=updated_content)

        note.refresh_from_db()

        self.assertEqual(note.user, self.user)
        self.assertEqual(note.contact, self.contact)
        self.assertEqual(note.content, updated_content)

    def test_can_delete_note(self):
        note = self.create_general_note(user=self.user)
        pk = note.pk
        self.assertEqual(Note.objects.filter(pk=pk).count(), 1)
        delete_note(note=note)
        self.assertEqual(Note.objects.filter(pk=pk).count(), 0)
