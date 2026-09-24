from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("note", "0001_initial"),
        ("pages", "0001_shorten_known_demo_text"),
    ]

    operations = [
        migrations.AlterField(model_name="note", name="content", field=models.CharField(max_length=250)),
    ]
