from .models import Task
from django import forms
from django.utils import timezone

from issue.models import Issue
from property.models import Property


class TaskForm(forms.ModelForm):
    def __init__(self, *args, user, parent_issue=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.parent_issue = parent_issue

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

        self.has_property_choices = self.fields["property"].queryset.exists()
        self.has_issue_choices = self.fields["issue"].queryset.exists()

        self.fields["property"].empty_label = (
            "Choose a property"
            if self.has_property_choices
            else "No active properties available"
        )
        self.fields["issue"].empty_label = (
            "Choose an issue"
            if self.has_issue_choices
            else "No active issues available"
        )

        if parent_issue is not None:
            self.fields.pop("property")
            self.fields.pop("issue")

        for field_name, field in self.fields.items():
            field.widget.attrs["autocomplete"] = "off"

            if field_name in ("property", "issue", "priority"):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"

    class Meta:
        model = Task
        fields = (
            "title", "description", "property", "issue", 
            "priority", "scheduled_date", "completion_deadline")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "scheduled_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date"},
            ),
            "completion_deadline": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date"},
            ),
        }

    def clean(self):
        cleaned_data = super().clean()

        if self.parent_issue is not None:
            return cleaned_data

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
