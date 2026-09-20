from .models import Note


def general_notes_for_user(*, user):
    return Note.objects.filter(
        user=user,
        contact__isnull=True,
    ).order_by("-created_at", "-pk")


def notes_for_contact(*, user, contact):
    return Note.objects.filter(
        user=user,
        contact=contact,
    ).order_by("-created_at", "-pk")