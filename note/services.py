from .models import Note


def create_note(*, user, content, contact=None):
    return Note.objects.create(
        user=user,
        content=content,
        contact=contact,
    )


def update_note(*, note, content):
    note.content = content
    note.save(update_fields=["content"])
    return note


def delete_note(*, note):
    note.delete()
