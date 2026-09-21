from django.db.models import OuterRef, Prefetch, Q, Subquery
from django.db.models.functions import Lower

from .models import Contact, ContactMethod

CONTACT_SORT_OPTIONS = {
    "name": (Lower("first_name"), Lower("last_name"), "pk"),
    "-name": (
        Lower("first_name").desc(),
        Lower("last_name").desc(),
        "pk",
    ),
    "created_at": ("created_at", "pk"),
    "-created_at": ("-created_at", "-pk"),
}


def contacts_for_user(*, user):
    first_method = ContactMethod.objects.filter(
        contact_id=OuterRef("pk"),
    ).order_by("pk")
    return Contact.objects.filter(
        user=user,
        deleted_at__isnull=True,
    ).annotate(
        first_email=Subquery(
            first_method.filter(type=ContactMethod.Type.EMAIL).values("value")[:1]
        ),
        first_telephone=Subquery(
            first_method.filter(type=ContactMethod.Type.TELEPHONE).values("value")[:1]
        ),
    ).prefetch_related(
        Prefetch(
            "contact_methods",
            queryset=ContactMethod.objects.order_by("type", "value", "pk"),
        )
    )


def filtered_contacts_for_user(
    *,
    user,
    search="",
    state="",
    sort="name",
):
    contacts = contacts_for_user(user=user)

    if search:
        contacts = contacts.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(contact_methods__value__icontains=search)
        ).distinct()

    if state in Contact.State.values:
        contacts = contacts.filter(state=state)

    ordering = CONTACT_SORT_OPTIONS.get(
        sort,
        CONTACT_SORT_OPTIONS["name"],
    )

    return contacts.order_by(*ordering)


def contact_methods_for_contact(*, contact):
    return ContactMethod.objects.filter(contact=contact).order_by(
        "type",
        "value",
        "pk",
    )
