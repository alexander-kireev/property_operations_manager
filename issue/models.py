from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from django.conf import settings


class Issue(models.Model):

    class State(models.TextChoices):
        ACTIVE = "active", "Active"
        RESOLVED = "resolved", "Resolved"
        DISMISSED = "dismissed", "Dismissed"

    class Priority(models.IntegerChoices):
        LOW = 1, "Low"
        MEDIUM = 2, "Medium"
        HIGH = 3, "High"
        URGENT = 4, "Urgent"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="issues"
    )

    property = models.ForeignKey(
        "property.Property",
        on_delete=models.SET_NULL,
        related_name="issues",
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

    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    resolution_deadline = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    terminated_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title


