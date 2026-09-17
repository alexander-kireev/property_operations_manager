from .models import Event, EventContact

from django.db.models.functions import Lower
from django.db.models import Q

EVENT_SORT_OPTIONS = {
    "title": (Lower("title"), "pk"),
    "-title": (Lower("title").desc(), "pk"),
    "created_at": ("created_at", "pk"),
    "-created_at": ("-created_at", "pk"),
    "scheduled_date": ("scheduled_date", "pk"),
    "-scheduled_date": ("-scheduled_date", "pk"),
}

USER_PARTICIPATION_REQUIRED_OPTIONS = {
    "required": True,
    "not_required": False,
}

USER_PRESENCE_REQUIRED_OPTIONS = {
    "required": True,
    "not_required": False,
}

def events_for_user(*, user):
    return Event.objects.select_related("property").filter(
        user=user,
        deleted_at__isnull=True,
    )

def filtered_events_for_user(
    *,
    user,
    search="",
    state="",
    sort="scheduled_date",
    property_id="",
    participation="",
    presence="",
):
    events = events_for_user(user=user)

    if search:
        events = events.filter(
            Q(title__icontains=search)
            | Q(description__icontains=search)
            | Q(property__name__icontains=search)
            | Q(property__address__icontains=search)
        ).distinct()

    if state in Event.State.values:
        events = events.filter(state=state)

    if participation in USER_PARTICIPATION_REQUIRED_OPTIONS:
        events = events.filter(
            user_participation_required=USER_PARTICIPATION_REQUIRED_OPTIONS[participation]
        )

    if presence in USER_PRESENCE_REQUIRED_OPTIONS:
        events = events.filter(
            user_presence_required=USER_PRESENCE_REQUIRED_OPTIONS[presence]
        )

    if property_id:
        events = events.filter(property_id=property_id)

    ordering = EVENT_SORT_OPTIONS.get(
        sort,
        EVENT_SORT_OPTIONS["scheduled_date"],
    )

    return events.order_by(*ordering)

def event_contacts_for_event(*, event):
    return EventContact.objects.select_related("contact").filter(event=event).order_by(
        "contact__first_name",
        "contact__last_name",
        "pk",
    )


def calendar_events_for_user(*, user, start_date, end_date, **filters):
    return filtered_events_for_user(
        user=user,
        **filters,
    ).filter(
        scheduled_date__range=(start_date, end_date),
    ).order_by(
        "scheduled_date",
        "-all_day",
        "start_time",
        Lower("title"),
        "pk",
    )
