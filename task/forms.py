from .models import Task
from django import forms
from django.utils import timezone

from issue.models import Issue
from property.models import Property


class TaskForm(forms.ModelForm):
    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        self.fields["property"].queryset = Property.objects.filter(
            user=user,
            state=Property.State.ACTIVE,
            deleted_at__isnull=True
        )

        self.fields["issue"].queryset = Issue.objects.filter(
            user=user,
            state=Issue.State.ACTIVE,
            terminated_at__isnull=True,
            deleted_at__isnull=True,
        )

        for field_name, field in self.fields.items():
            if field_name in ("property", "issue", "priority"):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"

    class Meta:
        model = Task
        fields = (
            "title", "description", "property", "issue", 
            "priority", "scheduled_date", "completion_deadline")

    def clean(self):
        cleaned_data = super().clean()
        property_record = cleaned_data.get("property")
        issue = cleaned_data.get("issue")

        if property_record is not None and issue is not None:
            raise forms.ValidationError(
                "A task cannot be related to both a property and an issue simultaneously."
            )

        return cleaned_data

    def clean_scheduled_date(self):
        scheduled_date = self.cleaned_data["scheduled_date"]

        if scheduled_date is not None and scheduled_date < timezone.localdate():
            raise forms.ValidationError(
                "A task can only be scheduled for today or later."
            )

        return scheduled_date

    def clean_completion_deadline(self):
        completion_deadline = self.cleaned_data["completion_deadline"]

        if completion_deadline is not None and completion_deadline < timezone.localdate():
            raise forms.ValidationError(
                "A task's deadline can only be set for today or later."
            )

        return completion_deadline