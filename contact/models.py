from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator, RegexValidator
from django.db import models
from django.db.models.functions import Lower
from django.conf import settings


email_validator = EmailValidator()


def normalise_contact_method_value(method_type, value):
    value = value.strip()
    if method_type == ContactMethod.Type.EMAIL:
        return value.lower()
    return value

e164_validator = RegexValidator(
    regex=r"^\+[1-9][0-9]{1,14}\Z",
    message="Enter an international number, for example +447700900123.",
)


class Contact(models.Model):

    class State(models.TextChoices):
        ACTIVE = "active", "Active"
        DEACTIVATED = "deactivated", "Deactivated"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contacts"
    )

    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.ACTIVE
    )

    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()


class ContactMethod(models.Model):

    class Meta:
        constraints = [
            models.UniqueConstraint(
                models.F("contact"),
                Lower("value"),
                name="unique_contact_method_value",
            ),
        ]

    class Type(models.TextChoices):
        EMAIL = "email", "Email"
        TELEPHONE = "telephone", "Telephone"

    contact = models.ForeignKey(
        "contact.Contact",
        on_delete=models.CASCADE,
        related_name="contact_methods",
    )

    type = models.CharField(
        max_length=20,
        choices=Type.choices,
    )

    value = models.CharField(max_length=254)


    def clean(self):
        super().clean()

        self.value = normalise_contact_method_value(self.type, self.value)

        # A form field may already have rejected the value; let that error stand.
        if not self.value:
            return

        try:
            if self.type == self.Type.EMAIL:
                email_validator(self.value)
            elif self.type == self.Type.TELEPHONE:
                e164_validator(self.value)
        except ValidationError as error:
            raise ValidationError({"value": error.messages}) from error

    def save(self, *args, **kwargs):
        self.value = normalise_contact_method_value(self.type, self.value)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_type_display()}: {self.value}"
