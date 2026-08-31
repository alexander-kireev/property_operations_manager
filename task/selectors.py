from datetime import timedelta

from django.db.models import Case, F, IntegerField, Q, Value, When
from django.db.models.functions import Lower
from django.utils import timezone

from .models import Task


TASK_SCHEDULE_PERIOD_OPTIONS = {
    "today": "Today",
    "next_7_days": "Next 7 days",
    "upcoming": "Upcoming",
    "past": "Past",
    "unscheduled": "Unscheduled",
}

TASK_DEADLINE_PERIOD_OPTIONS = {
    "overdue": "Overdue",
    "today": "Today",
    "next_7_days": "Next 7 days",
    "upcoming": "Upcoming",
    "no_deadline": "No deadline",
}

TASK_SORT_OPTIONS = {
    "title": (Lower("title"), "pk"),
    "-title": (Lower("title").desc(), "pk"),
    "-created_at": ("-created_at", "-pk"),
    "created_at": ("created_at", "pk"),
    "priority": ("priority", "pk"),
    "-priority": ("-priority", "pk"),
    "scheduled_date": (F("scheduled_date").asc(nulls_last=True), "pk"),
    "-scheduled_date": (F("scheduled_date").desc(nulls_last=True), "pk"),
    "completion_deadline": (
        F("completion_deadline").asc(nulls_last=True),
        "pk",
    ),
    "-completion_deadline": (
        F("completion_deadline").desc(nulls_last=True),
        "pk",
    ),
}


def tasks_for_user(*, user):
    return Task.objects.select_related("property", "issue").filter(
        user=user,
        deleted_at__isnull=True,
    )


def tasks_for_issue(*, user, issue):
    return tasks_for_user(user=user).filter(issue=issue).order_by(
        Case(
            When(state=Task.State.ACTIVE, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        ),
        F("completion_deadline").asc(nulls_last=True),
        "pk",
    )


def filtered_tasks_for_user(
    *,
    user,
    search="",
    state="",
    priority="",
    scheduled_period="",
    deadline_period="",
    sort="title",
):
    tasks = tasks_for_user(user=user)

    if search:
        tasks = tasks.filter(
            Q(title__icontains=search)
            | Q(description__icontains=search)
            | Q(issue__title__icontains=search)
            | Q(property__name__icontains=search)
            | Q(property__address__icontains=search)
        )

    if state in Task.State.values:
        tasks = tasks.filter(state=state)

    if priority in Task.Priority.values:
        tasks = tasks.filter(priority=priority)

    today = timezone.localdate()
    period_end = today + timedelta(days=6)

    if scheduled_period == "today":
        tasks = tasks.filter(scheduled_date=today)
    elif scheduled_period == "next_7_days":
        tasks = tasks.filter(scheduled_date__range=(today, period_end))
    elif scheduled_period == "upcoming":
        tasks = tasks.filter(scheduled_date__gte=today)
    elif scheduled_period == "past":
        tasks = tasks.filter(scheduled_date__lt=today)
    elif scheduled_period == "unscheduled":
        tasks = tasks.filter(scheduled_date__isnull=True)

    if deadline_period == "overdue":
        tasks = tasks.filter(
            state=Task.State.ACTIVE,
            completion_deadline__lt=today,
        )
    elif deadline_period == "today":
        tasks = tasks.filter(completion_deadline=today)
    elif deadline_period == "next_7_days":
        tasks = tasks.filter(completion_deadline__range=(today, period_end))
    elif deadline_period == "upcoming":
        tasks = tasks.filter(completion_deadline__gte=today)
    elif deadline_period == "no_deadline":
        tasks = tasks.filter(completion_deadline__isnull=True)

    ordering = TASK_SORT_OPTIONS.get(
        sort,
        TASK_SORT_OPTIONS["title"],
    )

    return tasks.order_by(*ordering)
