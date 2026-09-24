from django.db.models import Case, Count, F, IntegerField, OuterRef, Prefetch, Q, Subquery, Value, When
from django.db.models.functions import Coalesce, Lower

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
    method_total = (
        ContactMethod.objects.filter(contact_id=OuterRef("pk"))
        .order_by().values("contact_id")
        .annotate(total=Count("pk")).values("total")[:1]
    )
    return Contact.objects.filter(
        user=user,
        deleted_at__isnull=True,
    ).annotate(
        method_count=Coalesce(Subquery(method_total, output_field=IntegerField()), Value(0)),
        first_email=Subquery(
            first_method.filter(type=ContactMethod.Type.EMAIL).values("value")[:1]
        ),
        first_telephone=Subquery(
            first_method.filter(type=ContactMethod.Type.TELEPHONE).values("value")[:1]
        ),
    ).annotate(
        displayed_method_count=Case(
            When(first_email__isnull=False, first_telephone__isnull=False, then=Value(2)),
            When(first_email__isnull=False, then=Value(1)),
            When(first_telephone__isnull=False, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
    ).annotate(
        remaining_method_count=F("method_count") - F("displayed_method_count"),
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
