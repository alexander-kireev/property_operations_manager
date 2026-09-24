from django.db import migrations


# Only layout-test records are shortened. Unknown over-limit records stop the
# migration so operational text is never silently truncated.
LIMITS = (
    ("accounts", "User", "first_name", 50),
    ("accounts", "User", "last_name", 50),
    ("accounts", "PendingRegistration", "first_name", 50),
    ("accounts", "PendingRegistration", "last_name", 50),
    ("contact", "Contact", "first_name", 50),
    ("contact", "Contact", "last_name", 50),
    ("property", "Property", "name", 75),
    ("property", "Property", "address", 150),
    ("property", "Property", "description", 1000),
    ("issue", "Issue", "title", 100),
    ("issue", "Issue", "description", 1000),
    ("task", "Task", "title", 100),
    ("task", "Task", "description", 1000),
    ("event", "Event", "title", 100),
    ("event", "Event", "description", 1000),
    ("note", "Note", "content", 250),
)

KNOWN_PREFIXES = {
    ("contact", "Contact", "first_name"): (
        "[BOUNDARY CONTACT FIRST]", "[LAYOUT STRESS FIRST NAME]",
        "Hyphenated-and-multi-part-contact",
    ),
    ("contact", "Contact", "last_name"): (
        "[BOUNDARY CONTACT LAST]", "[LAYOUT STRESS LAST NAME]",
        "Very long family name",
    ),
    ("property", "Property", "name"): (
        "[BOUNDARY PROPERTY]", "[LAYOUT STRESS PROPERTY]",
        "A property name with many separate words",
    ),
    ("issue", "Issue", "title"): ("[BOUNDARY ISSUE]", "[LAYOUT STRESS ISSUE"),
    ("task", "Task", "title"): ("[BOUNDARY TASK]", "[LAYOUT STRESS TASK"),
    ("event", "Event", "title"): ("[BOUNDARY EVENT]", "[LAYOUT STRESS EVENT"),
    ("note", "Note", "content"): ("[1,000 CHARACTER CONTACT NOTE]",),
}

KNOWN_REPEATED = {
    ("contact", "Contact", "first_name"): ("N" * 150,),
    ("contact", "Contact", "last_name"): ("Z" * 150,),
    ("property", "Property", "name"): ("W" * 150,),
}


def shorten_known_demo_text(apps, schema_editor):
    updates = []
    unknown = []

    for app_label, model_name, field_name, limit in LIMITS:
        model = apps.get_model(app_label, model_name)
        key = (app_label, model_name, field_name)
        for record in model.objects.only("pk", field_name).iterator():
            value = getattr(record, field_name)
            if len(value) <= limit:
                continue
            known = value.startswith(KNOWN_PREFIXES.get(key, ())) or value in KNOWN_REPEATED.get(key, ())
            if known:
                updates.append((record, field_name, limit))
            else:
                unknown.append(f"{app_label}.{model_name}.{field_name} id={record.pk} ({len(value)} chars)")

    if unknown:
        raise RuntimeError(
            "Review over-limit operational text before changing field lengths: "
            + "; ".join(unknown)
        )

    for record, field_name, limit in updates:
        value = getattr(record, field_name)
        if field_name == "content":
            value = value.replace("[1,000 CHARACTER CONTACT NOTE]", "[250 CHARACTER CONTACT NOTE]", 1)
        setattr(record, field_name, value[:limit])
        record.save(update_fields=[field_name])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_pendingemailchange"),
        ("contact", "0002_contactmethod_unique_value"),
        ("event", "0002_remove_event_event_has_valid_timing_and_more"),
        ("issue", "0001_initial"),
        ("note", "0001_initial"),
        ("property", "0003_remove_property_unique_property_name_per_user_ci_and_more"),
        ("task", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(shorten_known_demo_text, migrations.RunPython.noop),
    ]
