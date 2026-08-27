from django.db.models import Q
from django.db.models.functions import Lower

from .models import Property


PROPERTY_SORT_OPTIONS = {
    "name": (Lower("name"), "pk"),
    "-name": (Lower("name").desc(), "pk"),
    "-created_at": ("-created_at", "-pk"),
    "created_at": ("created_at", "pk"),
}


def properties_for_user(*, user):
    return Property.objects.filter(
        user=user,
        deleted_at__isnull=True,
    )


def filtered_properties_for_user(
    *,
    user,
    search="",
    state="",
    sort="name",
):
    properties = properties_for_user(user=user)

    if search:
        properties = properties.filter(
            Q(name__icontains=search) | Q(address__icontains=search)
        )

    if state in Property.State.values:
        properties = properties.filter(state=state)

    ordering = PROPERTY_SORT_OPTIONS.get(
        sort,
        PROPERTY_SORT_OPTIONS["name"],
    )

    return properties.order_by(*ordering)
