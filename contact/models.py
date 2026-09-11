from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator, RegexValidator
from django.db import models
from django.conf import settings


email_validator = EmailValidator()

e164_validator = RegexValidator(
    regex=r"^\+[1-9][0-9]{1,14}\Z",
    message=(
        "Enter an international telephone number beginning with +, "
        "followed by 2–15 digits."
    ),
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

    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()


class ContactMethod(models.Model):

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

        try:
            if self.type == self.Type.EMAIL:
                email_validator(self.value)
            elif self.type == self.Type.TELEPHONE:
                e164_validator(self.value)
        except ValidationError as error:
            raise ValidationError({"value": error.messages}) from error

    def __str__(self):
        return f"{self.get_type_display()}: {self.value}"
