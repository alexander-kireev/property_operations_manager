from django.db import models
from django.db.models import F, Q

from django.conf import settings

class Event(models.Model):

    class Meta:
        constraints = [

            models.CheckConstraint(
                condition=(
                    Q(
                        all_day=True,
                        start_time__isnull=True,
                        end_time__isnull=True,
                    )
                    |
                    (
                        Q(
                            all_day=False,
                            start_time__isnull=False,
                        )
                        & (
                            Q(end_time__isnull=True)
                            | Q(start_time__lt=F("end_time"))
                        )
                    )
                ),
                name="event_has_valid_timing",
            ),

            models.CheckConstraint(
                condition=(
                    Q(user_presence_required=False)
                    | Q(user_participation_required=True)
                ),
                name="event_presence_requires_participation",
            )
        ]

    class State(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        OCCURRED = "occurred", "Occurred"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="events",
    )

    property = models.ForeignKey(
        "property.Property",
        on_delete=models.SET_NULL,
        related_name="events",
        null=True,
        blank=True,
    )

    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.SCHEDULED,
    )

    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    scheduled_date = models.DateField()
    all_day = models.BooleanField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    user_participation_required = models.BooleanField(default=False)
    user_presence_required = models.BooleanField(default=False)
    terminated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title


class EventContact(models.Model):

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("event", "contact"),
                name="unique_contact_attendance_per_event",
            ),
        ]

    contact = models.ForeignKey(
        "contact.Contact",
        on_delete=models.CASCADE,
        related_name="event_participations",
    )

    event = models.ForeignKey(
        "event.Event",
        on_delete=models.CASCADE,
        related_name="event_contacts",
    )
