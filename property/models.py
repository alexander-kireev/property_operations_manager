from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from django.conf import settings


class Property(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "user",
                condition=Q(deleted_at__isnull=True),
                name="unique_property_name_per_user_ci",
            ),
        ]

    class State(models.TextChoices):
        ACTIVE = "active", "Active"
        DEACTIVATED = "deactivated", "Deactivated"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="properties",
    )
    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.ACTIVE
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    address = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name
