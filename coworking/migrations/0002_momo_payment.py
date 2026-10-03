import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("coworking", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="booking",
            name="status",
            field=models.CharField(
                choices=[
                    ("payment_review", "Payment review"),
                    ("payment_pending", "Mobile money payment pending"),
                    ("payment_issue", "Payment received — availability issue"),
                    ("booked", "Booked"),
                    ("rejected", "Payment rejected"),
                    ("expired", "Hold expired"),
                    ("cancelled", "Cancelled"),
                ],
                db_index=True,
                default="payment_review",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="MoMoPayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("external_id", models.CharField(max_length=80, unique=True)),
                ("payer_number", models.CharField(max_length=20)),
                ("status", models.CharField(choices=[("pending", "Pending customer approval"), ("successful", "Successful"), ("failed", "Failed")], db_index=True, default="pending", max_length=16)),
                ("financial_transaction_id", models.CharField(blank=True, max_length=100)),
                ("provider_reason", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("booking", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="momo_payment", to="coworking.booking")),
            ],
        ),
    ]
