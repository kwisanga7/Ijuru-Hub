import calendar
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator


def end_date_for_period(start_date: date, period: str) -> date:
    """Return the inclusive last occupied date for one selected period."""
    if period == Booking.Period.DAY:
        return start_date
    if period == Booking.Period.WEEK:
        return start_date + timedelta(days=6)
    if period == Booking.Period.MONTH:
        if start_date.month == 12:
            year, month = start_date.year + 1, 1
        else:
            year, month = start_date.year, start_date.month + 1
        day = min(start_date.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)
    raise ValidationError("Choose one day, one week, or one month.")


class SpaceListing(models.Model):
    class Category(models.TextChoices):
        DESK = "desk", "Desk"
        PRIVATE_OFFICE = "private_office", "Private office"
        MEETING_ROOM = "meeting_room", "Meeting room"
        EVENT_SPACE = "event_space", "Event space"
        OTHER = "other", "Other"

    name = models.CharField(max_length=140)
    slug = models.SlugField(max_length=160, unique=True)
    category = models.CharField(max_length=24, choices=Category.choices)
    description = models.TextField()
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)], help_text="Number of equivalent spaces in this listing.")
    max_people = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)], help_text="Maximum people per space, if applicable.")
    currency_code = models.CharField(max_length=3, blank=True, help_text="Enter the client-approved currency code, for example RWF.")
    daily_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    weekly_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    monthly_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    photo = models.ImageField(upload_to="spaces/", blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return self.name

    def price_for(self, period):
        return {
            Booking.Period.DAY: self.daily_price,
            Booking.Period.WEEK: self.weekly_price,
            Booking.Period.MONTH: self.monthly_price,
        }[period]


class Booking(models.Model):
    class Period(models.TextChoices):
        DAY = "day", "One day"
        WEEK = "week", "One week"
        MONTH = "month", "One month"

    class Status(models.TextChoices):
        PAYMENT_REVIEW = "payment_review", "Payment review"
        PAYMENT_PENDING = "payment_pending", "Mobile money payment pending"
        PAYMENT_ISSUE = "payment_issue", "Payment received — availability issue"
        BOOKED = "booked", "Booked"
        REJECTED = "rejected", "Payment rejected"
        EXPIRED = "expired", "Hold expired"
        CANCELLED = "cancelled", "Cancelled"

    listing = models.ForeignKey(SpaceListing, on_delete=models.PROTECT, related_name="bookings")
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="coworking_bookings")
    period = models.CharField(max_length=8, choices=Period.choices)
    starts_on = models.DateField()
    ends_on = models.DateField(editable=False, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PAYMENT_REVIEW, db_index=True)
    amount_due = models.DecimalField(max_digits=12, decimal_places=2)
    currency_code = models.CharField(max_length=3, blank=True)
    payment_reference = models.CharField(max_length=140, blank=True, help_text="Optional reference or note for staff payment review.")
    review_note = models.TextField(blank=True, help_text="Staff-only payment review note.")
    qr_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    submitted_at = models.DateTimeField(default=timezone.now, db_index=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_coworking_bookings")
    checked_in_at = models.DateTimeField(null=True, blank=True)
    checked_out_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-submitted_at"]
        indexes = [models.Index(fields=["listing", "starts_on", "ends_on", "status"], name="booking_space_dates_status_idx")]

    def save(self, *args, **kwargs):
        self.ends_on = end_date_for_period(self.starts_on, self.period)
        super().save(*args, **kwargs)

    @property
    def payment_review_expires_at(self):
        return self.submitted_at + timedelta(hours=1)

    @property
    def payment_review_hold_active(self):
        return self.status == self.Status.PAYMENT_REVIEW and timezone.now() < self.payment_review_expires_at

    def __str__(self):
        return f"{self.listing} for {self.customer} ({self.get_status_display()})"


class MoMoPayment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending customer approval"
        SUCCESSFUL = "successful", "Successful"
        FAILED = "failed", "Failed"

    booking = models.OneToOneField(Booking, on_delete=models.PROTECT, related_name="momo_payment")
    reference_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    external_id = models.CharField(max_length=80, unique=True)
    payer_number = models.CharField(max_length=20)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    financial_transaction_id = models.CharField(max_length=100, blank=True)
    provider_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"MTN MoMo payment for booking #{self.booking_id} ({self.status})"


class Notification(models.Model):
    class Category(models.TextChoices):
        BOOKING = "booking", "Booking"
        PAYMENT = "payment", "Payment"
        VISIT = "visit", "Visit"
        ACCOUNT = "account", "Account"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    category = models.CharField(max_length=16, choices=Category.choices, default=Category.BOOKING)
    title = models.CharField(max_length=140)
    message = models.CharField(max_length=320)
    target_url = models.CharField(max_length=255, blank=True)
    dedupe_key = models.CharField(max_length=180, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "read_at", "created_at"], name="notif_user_read_created_idx")]

    def __str__(self):
        return f"{self.title} for {self.user}"


class MemberProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="member_profile")
    display_name = models.CharField(max_length=120, blank=True)
    job_title = models.CharField(max_length=120, blank=True)
    company = models.CharField(max_length=140, blank=True)
    bio = models.TextField(max_length=700, blank=True)
    website = models.URLField(max_length=200, blank=True)
    public_email = models.EmailField(blank=True)
    show_email = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.display_name or self.user.get_full_name() or self.user.username


class CommunityPost(models.Model):
    class Category(models.TextChoices):
        EVENT = "event", "Event"
        PROMOTION = "promotion", "Promotion"
        JOB = "job", "Job offer"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Published"
        REJECTED = "rejected", "Not approved"

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="community_posts")
    category = models.CharField(max_length=12, choices=Category.choices)
    title = models.CharField(max_length=120)
    body = models.TextField(max_length=1800)
    event_date = models.DateTimeField(null=True, blank=True, help_text="For events, enter the date and time.")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_community_posts")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
