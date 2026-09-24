from django import forms
from django.core.exceptions import ValidationError

from .models import (
    Contact,
    ContactMethod,
    e164_validator,
    email_validator,
    normalise_contact_method_value,
)

class ContactForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs["autocomplete"] = "off"
            field.widget.attrs["class"] = "form-control"

    class Meta:
        model = Contact
        fields = (
            "first_name",
            "last_name",
        )
        error_messages = {
            "first_name": {
                "max_length": "First name must be %(limit_value)d characters or fewer. You entered %(show_value)d.",
            },
            "last_name": {
                "max_length": "Last name must be %(limit_value)d characters or fewer. You entered %(show_value)d.",
            },
        }

class ContactCreateForm(ContactForm):
    email = forms.EmailField(
        required=False,
        max_length=254,
    )
    telephone = forms.CharField(
        required=False,
        max_length=16,
        validators=[e164_validator],
    )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class ContactMethodForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.contact = kwargs.pop("contact", None)
        super().__init__(*args, **kwargs)

        if self.contact is None and self.instance.pk:
            self.contact = self.instance.contact

        self.fields["type"].label = "Contact method"
        self.fields["type"].choices = [
            ("", "Choose email or telephone"),
            *ContactMethod.Type.choices,
        ]
        self.fields["value"].label = "Contact information"
        self.fields["type"].widget.attrs["class"] = "form-select"
        self.fields["value"].widget.attrs["class"] = "form-control"
        self.fields["value"].widget.attrs["autocomplete"] = "off"

    def clean(self):
        cleaned_data = super().clean()
        method_type = cleaned_data.get("type")
        value = cleaned_data.get("value")
        if method_type and value:
            value = normalise_contact_method_value(method_type, value)
            cleaned_data["value"] = value
            try:
                if method_type == ContactMethod.Type.EMAIL:
                    email_validator(value)
                elif method_type == ContactMethod.Type.TELEPHONE:
                    e164_validator(value)
            except ValidationError as error:
                self.add_error("value", error)
                return cleaned_data

            if self.contact is not None:
                duplicates = ContactMethod.objects.filter(
                    contact=self.contact,
                    value__iexact=value,
                ).exclude(pk=self.instance.pk)
                if duplicates.exists():
                    detail_name = (
                        "email address"
                        if method_type == ContactMethod.Type.EMAIL
                        else "telephone number"
                    )
                    self.add_error(
                        "value",
                        f"This {detail_name} is already saved for this contact.",
                    )
        return cleaned_data

    class Meta:
        model = ContactMethod
        fields = ("type", "value")
