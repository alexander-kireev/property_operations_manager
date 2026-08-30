from .models import Property
from django import forms



class PropertyForm(forms.ModelForm):
    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
            field.widget.attrs["autocomplete"] = "off"

    class Meta:
        model = Property
        fields = ("name", "description", "address")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }


    def clean_name(self):
        name = self.cleaned_data["name"]

        matching_properties = Property.objects.filter(
            user=self.user,
            name__iexact=name,
            deleted_at__isnull = True,
        )

        if self.instance.pk:
            matching_properties = matching_properties.exclude(
                pk=self.instance.pk
            )

        if matching_properties.exists():
            raise forms.ValidationError(
                "You already have a property with this name."
            )

        return name
