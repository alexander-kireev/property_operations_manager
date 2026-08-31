from django.db import transaction
from django.utils import timezone

from task.services import (
    delete_tasks_for_issue,
    dismiss_active_tasks_for_issue,
)

from .models import Issue


def create_issue(
    *, user, property, priority, title, description, resolution_deadline
):
    return Issue.objects.create(
        user=user,
        property=property,
        priority=priority,
        title=title,
        description=description,
        resolution_deadline=resolution_deadline,
    )


def update_issue(
    *, issue, property, priority, title, description, resolution_deadline
):
    issue.property = property
    issue.priority = priority
    issue.title = title
    issue.description = description
    issue.resolution_deadline = resolution_deadline
    issue.save(
        update_fields=[
            "property",
            "priority",
            "title",
            "description",
            "resolution_deadline",
        ]
    )
    return issue


@transaction.atomic
def resolve_issue(*, issue, dismiss_linked_tasks=False):
    if issue.state != Issue.State.ACTIVE:
        return issue

    terminated_at = timezone.now()
    issue.state = Issue.State.RESOLVED
    issue.terminated_at = terminated_at
    issue.save(update_fields=["state", "terminated_at"])

    if dismiss_linked_tasks:
        dismiss_active_tasks_for_issue(
            issue=issue,
            terminated_at=terminated_at,
        )

    return issue


@transaction.atomic
def dismiss_issue(*, issue, dismiss_linked_tasks=False):
    if issue.state != Issue.State.ACTIVE:
        return issue

    terminated_at = timezone.now()
    issue.state = Issue.State.DISMISSED
    issue.terminated_at = terminated_at
    issue.save(update_fields=["state", "terminated_at"])

    if dismiss_linked_tasks:
        dismiss_active_tasks_for_issue(
            issue=issue,
            terminated_at=terminated_at,
        )

    return issue


def reactivate_issue(*, issue):
    if issue.state == Issue.State.ACTIVE:
        return issue

    issue.state = Issue.State.ACTIVE
    issue.terminated_at = None
    issue.save(update_fields=["state", "terminated_at"])
    return issue


@transaction.atomic
def delete_issue(*, issue, delete_linked_tasks=False):
    if issue.deleted_at is not None:
        return issue

    deleted_at = timezone.now()
    issue.deleted_at = deleted_at
    issue.save(update_fields=["deleted_at"])

    if delete_linked_tasks:
        delete_tasks_for_issue(issue=issue, deleted_at=deleted_at)

    return issue
