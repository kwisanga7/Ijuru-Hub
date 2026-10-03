# Generated as the initial Ijuru Hub schema.
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="SpaceListing",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=140)),
                ("slug", models.SlugField(max_length=160, unique=True)),
                ("category", models.CharField(choices=[("desk", "Desk"), ("private_office", "Private office"), ("meeting_room", "Meeting room"), ("event_space", "Event space"), ("other", "Other")], max_length=24)),
                ("description", models.TextField()),
                ("quantity", models.PositiveIntegerField(default=1, help_text="Number of equivalent spaces in this listing.", validators=[django.core.validators.MinValueValidator(1)])),
                ("max_people", models.PositiveIntegerField(default=1, help_text="Maximum people per space, if applicable.", validators=[django.core.validators.MinValueValidator(1)])),
                ("daily_price", models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal("0.01"))])),
                ("weekly_price", models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal("0.01"))])),
                ("monthly_price", models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal("0.01"))])),
                ("photo", models.ImageField(blank=True, upload_to="spaces/")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["category", "name"]},
        ),
        migrations.CreateModel(
            name="Booking",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("period", models.CharField(choices=[("day", "One day"), ("week", "One week"), ("month", "One month")], max_length=8)),
                ("starts_on", models.DateField()),
                ("ends_on", models.DateField(db_index=True, editable=False)),
                ("status", models.CharField(choices=[("payment_review", "Payment review"), ("booked", "Booked"), ("rejected", "Payment rejected"), ("expired", "Hold expired"), ("cancelled", "Cancelled")], db_index=True, default="payment_review", max_length=20)),
                ("amount_due", models.DecimalField(decimal_places=2, max_digits=12)),
                ("payment_reference", models.CharField(blank=True, help_text="Optional reference or note for staff payment review.", max_length=140)),
                ("review_note", models.TextField(blank=True, help_text="Staff-only payment review note.")),
                ("qr_token", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("submitted_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("checked_in_at", models.DateTimeField(blank=True, null=True)),
                ("checked_out_at", models.DateTimeField(blank=True, null=True)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="coworking_bookings", to=settings.AUTH_USER_MODEL)),
                ("listing", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bookings", to="coworking.spacelisting")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_coworking_bookings", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-submitted_at"]},
        ),
        migrations.AddIndex(
            model_name="booking",
            index=models.Index(fields=["listing", "starts_on", "ends_on", "status"], name="booking_space_dates_status_idx"),
        ),
    ]
