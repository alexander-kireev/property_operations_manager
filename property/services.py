from django.utils import timezone

from .models import Property


def create_property(*, user, name, description="", address=""):
    return Property.objects.create(
        user=user,
        name=name,
        description=description,
        address=address,
    )


def update_property(*, property_record, name, description="", address=""):
    property_record.name = name
    property_record.description = description
    property_record.address = address
    property_record.save(update_fields=["name", "description", "address"])

    return property_record


def deactivate_property(*, property_record):
    if property_record.state == Property.State.DEACTIVATED:
        return property_record

    property_record.state = Property.State.DEACTIVATED
    property_record.save(update_fields=["state"])

    return property_record


def reactivate_property(*, property_record):
    if property_record.state == Property.State.ACTIVE:
        return property_record

    property_record.state = Property.State.ACTIVE
    property_record.save(update_fields=["state"])

    return property_record


def delete_property(*, property_record):
    if property_record.deleted_at is not None:
        return property_record

    property_record.deleted_at = timezone.now()
    property_record.save(update_fields=["deleted_at"])

    return property_record
