from django import forms
from django.db.models import Q
from .models import Event

from property.models import Property
from contact.models import Contact
from contact.selectors import contacts_for_user

class EventForm(forms.ModelForm):
    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)

        properties = Property.objects.filter(
            user=user,
            state=Property.State.ACTIVE,
            deleted_at__isnull=True,
        )

        if self.instance.pk and self.instance.property_id:
            properties = Property.objects.filter(
                Q(
                    user=user,
                    state=Property.State.ACTIVE,
                    deleted_at__isnull=True,
                )
                | Q(
                    pk=self.instance.property_id,
                    user=user,
                    deleted_at__isnull=True,
                )
            )

        self.fields["property"].queryset = properties.order_by("name", "pk")
        self.fields["property"].empty_label = "No property"

        form_control_fields = (
            "title",
            "description",
            "scheduled_date",
            "start_time",
            "end_time",
        )

        form_select_fields = (
            "property",
        )

        form_input_fields = (
            "all_day",
            "user_participation_required",
            "user_presence_required",
        )

        
        for field_name, field in self.fields.items():
            if field_name in form_select_fields:
                field.widget.attrs["class"] = "form-select"
            elif field_name in form_control_fields:
                field.widget.attrs["class"] = "form-control"
                field.widget.attrs["autocomplete"] = "off"
            elif field_name in form_input_fields:
                field.widget.attrs["class"] = "form-check-input"


    class Meta:
        model = Event
        fields = (
            "property",
            "title",
            "description",
            "scheduled_date",
            "all_day",
            "start_time",
            "end_time",
            "user_participation_required",
            "user_presence_required",
        )

        widgets = {
            "scheduled_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date"},
            ),
            "start_time": forms.TimeInput(
                format="%H:%M",
                attrs={"type": "text", "maxlength": 5},
            ),
            "end_time": forms.TimeInput(
                format="%H:%M",
                attrs={"type": "text", "maxlength": 5},
            ),
            "description": forms.Textarea(
                attrs={"rows": 3}
            ),
        }

    def clean(self):
        cleaned_data = super().clean()

        all_day = cleaned_data.get("all_day")
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        user_participation_required = cleaned_data.get("user_participation_required")
        user_presence_required = cleaned_data.get("user_presence_required")

        if all_day:
            if start_time is not None:
                self.add_error("start_time", "An all-day event cannot have a start time.")

            if end_time is not None:
                self.add_error("end_time", "An all-day event cannot have an end time.")

        else:
            if start_time is None:
                self.add_error("start_time", "Enter a start time.")

            if end_time is not None and start_time is not None and end_time <= start_time:
                self.add_error(
                    "end_time",
                    "End time must be later than start time."
                )

        if user_presence_required and not user_participation_required:
            self.add_error(
                "user_participation_required",
                "You must participate in an event if you are attending it."
            )

        return cleaned_data


class EventContactForm(forms.Form):
    def __init__(self, *args, user, event=None, **kwargs):
        super().__init__(*args, **kwargs)

        contacts = contacts_for_user(user=user).filter(
            state=Contact.State.ACTIVE,
        )

        if event is not None and event.pk:
            contacts = contacts.exclude(
                event_participations__event=event
            )

        self.fields["contacts"].queryset = contacts.order_by(
            "first_name",
            "last_name",
            "pk",
        )

    contacts = forms.ModelMultipleChoiceField(
        queryset=Contact.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(),
    )

