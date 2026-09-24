from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from django.conf import settings


class Task(models.Model):
    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(property__isnull=True)
                    | Q(issue__isnull=True)
                ),
                name="task_has_at_most_one_parent",
            ),
        ]

    class State(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        DISMISSED = "dismissed", "Dismissed"


    class Priority(models.IntegerChoices):
        LOW = 1, "Low"
        MEDIUM = 2, "Medium"
        HIGH = 3, "High"
        URGENT = 4, "Urgent"


    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tasks"
    )

    property = models.ForeignKey(
        "property.Property",
        on_delete=models.SET_NULL,
        related_name="tasks",
        null=True,
        blank=True
    )

    issue = models.ForeignKey(
        "issue.Issue",
        on_delete=models.SET_NULL,
        related_name="tasks",
        null=True,
        blank=True
    )

    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.ACTIVE
    )
    priority = models.PositiveIntegerField(
        choices=Priority.choices,
        default=Priority.LOW
    )
    title = models.CharField(max_length=100)
    description = models.CharField(max_length=1000, blank=True)
    scheduled_date = models.DateField(null=True, blank=True)
    completion_deadline = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    terminated_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title
