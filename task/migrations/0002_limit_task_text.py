from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("task", "0001_initial"),
        ("pages", "0001_shorten_known_demo_text"),
    ]

    operations = [
        migrations.AlterField(model_name="task", name="description", field=models.CharField(blank=True, max_length=1000)),
        migrations.AlterField(model_name="task", name="title", field=models.CharField(max_length=100)),
    ]
