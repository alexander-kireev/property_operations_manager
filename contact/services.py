from django.db import transaction
from django.utils import timezone

from .models import Contact, ContactMethod


@transaction.atomic
def create_contact(
    *,
    user,
    first_name,
    last_name="",
    email="",
    telephone="",
):
    contact = Contact.objects.create(
        user=user,
        first_name=first_name,
        last_name=last_name,
    )

    if email:
        ContactMethod.objects.create(
            contact=contact,
            type=ContactMethod.Type.EMAIL,
            value=email,
        )

    if telephone:
        ContactMethod.objects.create(
            contact=contact,
            type=ContactMethod.Type.TELEPHONE,
            value=telephone,
        )

    return contact


def update_contact(*, contact, first_name, last_name=""):
    contact.first_name = first_name
    contact.last_name = last_name
    contact.save(update_fields=["first_name", "last_name"])
    return contact


def deactivate_contact(*, contact):
    if contact.state == Contact.State.DEACTIVATED:
        return contact

    contact.state = Contact.State.DEACTIVATED
    contact.save(update_fields=["state"])
    return contact


def reactivate_contact(*, contact):
    if contact.state == Contact.State.ACTIVE:
        return contact

    contact.state = Contact.State.ACTIVE
    contact.save(update_fields=["state"])
    return contact


def delete_contact(*, contact):
    if contact.deleted_at is not None:
        return contact

    contact.deleted_at = timezone.now()
    contact.save(update_fields=["deleted_at"])
    return contact


def create_contact_method(*, contact, type, value):
    return ContactMethod.objects.create(
        contact=contact,
        type=type,
        value=value,
    )


def update_contact_method(*, contact_method, type, value):
    contact_method.type = type
    contact_method.value = value
    contact_method.save(update_fields=["type", "value"])
    return contact_method


def delete_contact_method(*, contact_method):
    contact_method.delete()
