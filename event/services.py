from .models import Event, EventContact
from contact.models import Contact
from django.db import transaction
from django.utils import timezone


def _validate_property_ownership(*, user, property):
    if property is None:
        return
    if property.user_id != user.pk or property.deleted_at is not None:
        raise ValueError("Property must belong to the Event owner.")


def _validated_contacts(*, user, contacts):
    contacts = list(contacts)
    if any(contact.pk is None for contact in contacts):
        raise ValueError("Contacts must be saved before they can be added.")
    contacts_by_id = {
        contact.pk: contact
        for contact in contacts
    }
    contact_ids = set(contacts_by_id)
    valid_contacts = list(Contact.objects.filter(
        pk__in=contact_ids,
        user=user,
        state=Contact.State.ACTIVE,
        deleted_at__isnull=True,
    ))
    if len(valid_contacts) != len(contact_ids):
        raise ValueError("Contacts must be active Contacts owned by the Event owner.")
    return valid_contacts


@transaction.atomic
def create_event(
    *,
    user,
    title,
    description="",
    property=None,
    all_day,
    scheduled_date,
    start_time=None,
    end_time=None,
    user_participation_required,
    user_presence_required,
    contacts=(),
):
    _validate_property_ownership(user=user, property=property)
    event = Event.objects.create(
        user=user,
        title=title,
        description=description,
        property=property,
        all_day=all_day,
        scheduled_date=scheduled_date,
        start_time=start_time,
        end_time=end_time,
        user_participation_required=user_participation_required,
        user_presence_required=user_presence_required,
    )
    add_contacts_to_event(event=event, contacts=contacts)
    return event


def delete_event(*, event):
    if event.deleted_at is not None:
        return event

    event.deleted_at = timezone.now()
    event.save(update_fields=["deleted_at"])
    return event


def update_event(
    *,
    event,
    title,
    description="",
    property=None,
    all_day,
    scheduled_date,
    start_time=None,
    end_time=None,
    user_participation_required,
    user_presence_required,
):
    _validate_property_ownership(user=event.user, property=property)
    event.title = title
    event.description = description
    event.property = property
    event.all_day = all_day
    event.scheduled_date = scheduled_date
    event.start_time = start_time
    event.end_time = end_time
    event.user_participation_required = user_participation_required
    event.user_presence_required = user_presence_required
    event.save(update_fields=[
        "title",
        "description",
        "property",
        "all_day",
        "scheduled_date",
        "start_time",
        "end_time",
        "user_participation_required",
        "user_presence_required",
    ])
    return event


def mark_event_occurred(*, event):
    if event.state != Event.State.SCHEDULED:
        return event
    
    event.state = Event.State.OCCURRED
    event.terminated_at = timezone.now()
    event.save(update_fields=["state", "terminated_at"])
    return event


def cancel_event(*, event):
    if event.state != Event.State.SCHEDULED:
        return event
    
    event.state = Event.State.CANCELLED
    event.terminated_at = timezone.now()
    event.save(update_fields=["state", "terminated_at"])
    return event


def reactivate_event(*, event):
    if event.state == Event.State.SCHEDULED:
        return event

    event.state = Event.State.SCHEDULED
    event.terminated_at = None
    event.save(update_fields=["state", "terminated_at"])
    return event


@transaction.atomic
def add_contacts_to_event(*, event, contacts):
    if event.deleted_at is not None or event.state != Event.State.SCHEDULED:
        return event

    contacts = _validated_contacts(user=event.user, contacts=contacts)
    existing_ids = set(EventContact.objects.filter(
        event=event,
        contact_id__in=[contact.pk for contact in contacts],
    ).values_list("contact_id", flat=True))

    EventContact.objects.bulk_create(
        [
            EventContact(event=event, contact=contact)
            for contact in contacts
            if contact.pk not in existing_ids
        ],
        ignore_conflicts=True,
    )
    return event


def remove_contact_from_event(*, event_contact):
    event = event_contact.event
    if event.deleted_at is not None or event.state != Event.State.SCHEDULED:
        return event
    event_contact.delete()
    return event
