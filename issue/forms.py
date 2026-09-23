from django import forms
from django.db.models import Q

from property.models import Property

from .models import Issue


class IssueForm(forms.ModelForm):
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
        self.fields["resolution_deadline"].label = "Resolve by"

        for field_name, field in self.fields.items():
            field.widget.attrs["autocomplete"] = "off"
            field.widget.attrs["class"] = (
                "form-select"
                if field_name in ("property", "priority")
                else "form-control"
            )

    class Meta:
        model = Issue
        fields = (
            "title",
            "description",
            "property",
            "priority",
            "resolution_deadline",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "resolution_deadline": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date"},
            ),
        }
