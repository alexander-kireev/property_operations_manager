from django.db import models

from django.conf import settings


class Note(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notes",
    )

    contact = models.ForeignKey(
        "contact.Contact",
        on_delete=models.CASCADE,
        related_name="notes",
        null=True,
        blank=True,
    )

    content = models.CharField(max_length=250)
    created_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return self.content
