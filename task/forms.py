from .models import Task
from django import forms

from issue.models import Issue
from property.models import Property


class TaskForm(forms.ModelForm):
    def __init__(self, *args, user, parent_issue=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.parent_issue = parent_issue

        active_properties = Property.objects.filter(
            user=user,
            state=Property.State.ACTIVE,
            deleted_at__isnull=True
        )

        active_issues = Issue.objects.filter(
            user=user,
            state=Issue.State.ACTIVE,
            terminated_at__isnull=True,
            deleted_at__isnull=True,
        )

        # Keep an existing historical parent selectable while editing, but never
        # offer it as a new relationship on another task.
        self.fields["property"].queryset = active_properties
        self.fields["issue"].queryset = active_issues
        if self.instance.pk and self.instance.property_id:
            self.fields["property"].queryset = (
                active_properties | Property.objects.filter(
                    user=user, pk=self.instance.property_id,
                )
            )
        if self.instance.pk and self.instance.issue_id:
            self.fields["issue"].queryset = (
                active_issues | Issue.objects.filter(
                    user=user, pk=self.instance.issue_id,
                )
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
            "description": forms.Textarea(attrs={"rows": 3}),
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
        relationship_type = self.data.get("relationship_type") if self.is_bound else None

        if not relationship_type and not property_record and not issue and self.instance.pk:
            if self.instance.issue_id:
                cleaned_data["issue"] = self.instance.issue
                issue = self.instance.issue
            elif self.instance.property_id:
                cleaned_data["property"] = self.instance.property
                property_record = self.instance.property

        if relationship_type not in (None, "", "standalone", "property", "issue"):
            raise forms.ValidationError("Choose a valid task relationship.")

        if relationship_type == "standalone":
            cleaned_data["property"] = None
            cleaned_data["issue"] = None
            return cleaned_data
        if relationship_type == "property":
            cleaned_data["issue"] = None
            if property_record is None and "property" not in self.errors:
                self.add_error("property", "Choose a property.")
            return cleaned_data
        if relationship_type == "issue":
            cleaned_data["property"] = None
            if issue is None and "issue" not in self.errors:
                self.add_error("issue", "Choose an issue.")
            return cleaned_data

        if property_record is not None and issue is not None:
            raise forms.ValidationError(
                "A task cannot be related to both a property and an issue simultaneously."
            )

        return cleaned_data
