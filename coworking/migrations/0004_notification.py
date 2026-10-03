from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("coworking", "0003_merge_0002_currency_code_0002_momo_payment"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("category", models.CharField(choices=[("booking", "Booking"), ("payment", "Payment"), ("visit", "Visit"), ("account", "Account")], default="booking", max_length=16)),
                ("title", models.CharField(max_length=140)),
                ("message", models.CharField(max_length=320)),
                ("target_url", models.CharField(blank=True, max_length=255)),
                ("dedupe_key", models.CharField(blank=True, max_length=180, null=True, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("read_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["user", "read_at", "created_at"], name="notif_user_read_created_idx"),
        ),
    ]
