from django.utils import timezone

from .models import Task


def create_task(*, user, property, issue, priority, title,
                description, scheduled_date, completion_deadline):
    return Task.objects.create(
        user=user,
        property=property,
        issue=issue,
        priority=priority,
        title=title,
        description=description,
        scheduled_date=scheduled_date,
        completion_deadline=completion_deadline
    )


def update_task(*, task, property, issue, priority, title, description,
                    scheduled_date, completion_deadline):
    task.property = property
    task.issue = issue
    task.priority = priority
    task.title = title
    task.description = description
    task.scheduled_date = scheduled_date
    task.completion_deadline = completion_deadline
    task.save(update_fields=["property", "issue", "priority", "title",
                             "description", "scheduled_date", "completion_deadline"])

    return task

def dismiss_task(*, task):
    if task.state == Task.State.COMPLETED or task.state == Task.State.DISMISSED:
        return task

    task.state = Task.State.DISMISSED
    task.terminated_at = timezone.now()
    task.save(update_fields=["state", "terminated_at"])

    return task

def complete_task(*, task):
    if task.state == Task.State.COMPLETED or task.state == Task.State.DISMISSED:
        return task

    task.state = Task.State.COMPLETED
    task.terminated_at = timezone.now()
    task.save(update_fields=["state", "terminated_at"])

    return task

def reactivate_task(*, task):
    if task.state == Task.State.ACTIVE:
        return task

    task.state = Task.State.ACTIVE
    task.terminated_at = None
    task.save(update_fields=["state", "terminated_at"])

    return task

def delete_task(*, task):
    if task.deleted_at is not None:
        return task

    task.deleted_at = timezone.now()
    task.save(update_fields=["deleted_at"])

    return task