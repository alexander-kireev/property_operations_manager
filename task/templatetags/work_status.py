from dataclasses import dataclass

from django import template
from django.utils import timezone


register = template.Library()
DUE_SOON_DAYS = 3


@dataclass(frozen=True)
class WorkStatus:
    kind: str
    headline: str
    explanation: str
    list_label: str = ""


def status_for(record, *, today=None):
    today = today or timezone.localdate()
    state = record.state
    if state != "active":
        return WorkStatus("terminal", record.get_state_display(), "Dates retained as history.")

    deadline = getattr(record, "completion_deadline", None)
    if deadline is None:
        deadline = getattr(record, "resolution_deadline", None)
    if deadline is not None:
        days = (deadline - today).days
        if days < 0:
            overdue_days = -days
            unit = "day" if overdue_days == 1 else "days"
            return WorkStatus(
                "overdue", f"Overdue by {overdue_days} {unit}",
                "Still active · deadline passed.", "Overdue",
            )
        if days <= DUE_SOON_DAYS:
            headline = "Due today" if days == 0 else f"Due in {days} {'day' if days == 1 else 'days'}"
            return WorkStatus("soon", headline, "Still active · deadline approaching.", "Due soon")

    scheduled = getattr(record, "scheduled_date", None)
    if scheduled is not None and scheduled < today:
        return WorkStatus(
            "missed", "Scheduled date passed", "Still active · scheduled date passed.",
            "Past scheduled",
        )
    if deadline is not None:
        return WorkStatus("neutral", "On track", "This work remains active.")
    return WorkStatus("neutral", "Active", "No deadline set.")


@register.simple_tag
def work_status(record, today=None):
    return status_for(record, today=today)


@register.filter
def relative_day(value, today=None):
    if value is None:
        return "Not set"
    today = today or timezone.localdate()
    days = (value - today).days
    if days == 0:
        return "Today"
    if days == -1:
        return "Yesterday"
    if days == 1:
        return "Tomorrow"
    return f"{abs(days)} days ago" if days < 0 else f"In {days} days"
