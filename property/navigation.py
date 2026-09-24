from urllib.parse import urlencode

from django.urls import reverse

from .models import Property


def active_property_for_user(user, value):
    """Only accept a property that the user can still add records to."""
    if not str(value).isdigit():
        return None
    return Property.objects.filter(
        pk=value,
        user=user,
        state=Property.State.ACTIVE,
        deleted_at__isnull=True,
    ).first()


def created_record_property_url(record, value, record_type):
    """Return to the origin only if the new record actually belongs there."""
    if not str(value).isdigit():
        return None
    property_id = record.property_id
    if property_id is None and record_type == "task" and record.issue_id:
        property_id = record.issue.property_id
    if str(property_id) != str(value):
        return None
    query = urlencode({
        "records_type": record_type,
        "records_scope": "current",
        "records_sort": "recent",
    })
    return f"{reverse('property:property_detail', args=[property_id])}?{query}"
