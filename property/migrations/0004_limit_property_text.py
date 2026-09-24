from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("property", "0003_remove_property_unique_property_name_per_user_ci_and_more"),
        ("pages", "0001_shorten_known_demo_text"),
    ]

    operations = [
        migrations.AlterField(model_name="property", name="address", field=models.CharField(blank=True, max_length=150)),
        migrations.AlterField(model_name="property", name="description", field=models.CharField(blank=True, max_length=1000)),
        migrations.AlterField(model_name="property", name="name", field=models.CharField(max_length=75)),
    ]
