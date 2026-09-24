from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("event", "0002_remove_event_event_has_valid_timing_and_more"),
        ("pages", "0001_shorten_known_demo_text"),
    ]

    operations = [
        migrations.AlterField(model_name="event", name="description", field=models.CharField(blank=True, max_length=1000)),
        migrations.AlterField(model_name="event", name="title", field=models.CharField(max_length=100)),
    ]
