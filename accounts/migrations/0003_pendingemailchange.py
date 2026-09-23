import accounts.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_pendingregistration_alter_user_options_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="PendingEmailChange",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("old_email", models.EmailField(max_length=254)),
                ("new_email", models.EmailField(max_length=254)),
                ("token_hash", models.CharField(editable=False, max_length=64, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField(default=accounts.models.pending_email_change_expiry)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="pending_email_change", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
