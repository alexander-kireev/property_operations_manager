from datetime import timedelta

from django.db.models import F, Q
from django.db.models.functions import Lower
from django.utils import timezone

from .models import Issue


ISSUE_DEADLINE_PERIOD_OPTIONS = {
    "overdue": "Overdue",
    "today": "Today",
    "next_7_days": "Next 7 days",
    "upcoming": "Upcoming",
    "no_deadline": "No deadline",
}

ISSUE_SORT_OPTIONS = {
    "title": (Lower("title"), "pk"),
    "-title": (Lower("title").desc(), "pk"),
    "-created_at": ("-created_at", "-pk"),
    "created_at": ("created_at", "pk"),
    "priority": ("priority", "pk"),
    "-priority": ("-priority", "pk"),
    "resolution_deadline": (
        F("resolution_deadline").asc(nulls_last=True),
        "pk",
    ),
    "-resolution_deadline": (
        F("resolution_deadline").desc(nulls_last=True),
        "pk",
    ),
}


def issues_for_user(*, user):
    return Issue.objects.select_related("property").filter(
        user=user,
        deleted_at__isnull=True,
    )


def filtered_issues_for_user(
    *,
    user,
    search="",
    state="",
    priority="",
    property_id="",
    deadline_period="",
    sort="title",
):
    issues = issues_for_user(user=user)

    if search:
        issues = issues.filter(
            Q(title__icontains=search)
            | Q(description__icontains=search)
            | Q(property__name__icontains=search)
            | Q(property__address__icontains=search)
        )

    if state in Issue.State.values:
        issues = issues.filter(state=state)

    if priority in Issue.Priority.values:
        issues = issues.filter(priority=priority)

    if property_id:
        issues = issues.filter(property_id=property_id)

    today = timezone.localdate()
    period_end = today + timedelta(days=6)

    if deadline_period == "overdue":
        issues = issues.filter(
            state=Issue.State.ACTIVE,
            resolution_deadline__lt=today,
        )
    elif deadline_period == "today":
        issues = issues.filter(resolution_deadline=today)
    elif deadline_period == "next_7_days":
        issues = issues.filter(resolution_deadline__range=(today, period_end))
    elif deadline_period == "upcoming":
        issues = issues.filter(resolution_deadline__gte=today)
    elif deadline_period == "no_deadline":
        issues = issues.filter(resolution_deadline__isnull=True)

    ordering = ISSUE_SORT_OPTIONS.get(sort, ISSUE_SORT_OPTIONS["title"])
    return issues.order_by(*ordering)
