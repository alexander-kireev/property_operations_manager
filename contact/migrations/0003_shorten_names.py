from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contact", "0002_contactmethod_unique_value"),
        ("pages", "0001_shorten_known_demo_text"),
    ]

    operations = [
        migrations.AlterField(model_name="contact", name="first_name", field=models.CharField(max_length=50)),
        migrations.AlterField(model_name="contact", name="last_name", field=models.CharField(blank=True, max_length=50)),
    ]
