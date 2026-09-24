from django.db.models import Count, Min, Q
from django.db.models.functions import Lower
from django.utils import timezone

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


def with_work_summary(properties):
    """Counts for visible property work, without multiplying joined rows."""
    return properties.annotate(
        open_issues=Count(
            "issues", filter=Q(issues__state="active", issues__deleted_at__isnull=True), distinct=True,
        ),
        open_direct_tasks=Count(
            "tasks", filter=Q(tasks__state="active", tasks__deleted_at__isnull=True), distinct=True,
        ),
        open_issue_tasks=Count(
            "issues__tasks",
            filter=Q(issues__tasks__state="active", issues__tasks__deleted_at__isnull=True, issues__deleted_at__isnull=True),
            distinct=True,
        ),
        next_event_date=Min(
            "events__scheduled_date",
            filter=Q(events__state="scheduled", events__deleted_at__isnull=True, events__scheduled_date__gte=timezone.localdate()),
        ),
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
