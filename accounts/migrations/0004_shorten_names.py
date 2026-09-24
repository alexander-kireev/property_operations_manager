from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_pendingemailchange"),
        ("pages", "0001_shorten_known_demo_text"),
    ]

    operations = [
        migrations.AlterField(model_name="pendingregistration", name="first_name", field=models.CharField(max_length=50)),
        migrations.AlterField(model_name="pendingregistration", name="last_name", field=models.CharField(max_length=50)),
        migrations.AlterField(model_name="user", name="first_name", field=models.CharField(max_length=50)),
        migrations.AlterField(model_name="user", name="last_name", field=models.CharField(max_length=50)),
    ]
