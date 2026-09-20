from django import forms
from .models import Note


class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = (
            "content",
        )

        widgets = {
            "content": forms.Textarea(attrs={
                "rows": 2,
                "class": "form-control",
                "placeholder": "New note...",
                }
            )
        }
