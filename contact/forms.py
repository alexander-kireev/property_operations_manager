from django import forms

from .models import Contact, ContactMethod, e164_validator

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


class ContactMethodForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["type"].widget.attrs["class"] = "form-select"
        self.fields["value"].widget.attrs["class"] = "form-control"
        self.fields["value"].widget.attrs["autocomplete"] = "off"

    class Meta:
        model = ContactMethod
        fields = ("type", "value")
