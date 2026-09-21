from django.db import migrations, models
from django.db.models.functions import Lower


def normalise_and_deduplicate_methods(apps, schema_editor):
    ContactMethod = apps.get_model("contact", "ContactMethod")
    seen = set()

    for method in ContactMethod.objects.order_by("pk").iterator():
        value = method.value.strip()
        if method.type == "email":
            value = value.lower()

        key = (method.contact_id, value.lower())
        if key in seen:
            method.delete()
            continue

        seen.add(key)
        if method.value != value:
            method.value = value
            method.save(update_fields=["value"])


class Migration(migrations.Migration):

    dependencies = [
        ("contact", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            normalise_and_deduplicate_methods,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="contactmethod",
            constraint=models.UniqueConstraint(
                models.F("contact"),
                Lower("value"),
                name="unique_contact_method_value",
            ),
        ),
    ]
