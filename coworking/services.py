from datetime import timedelta
import base64
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.urls import reverse

from .models import Booking, MoMoPayment, SpaceListing, end_date_for_period
from .notifications import notify_staff, notify_user


ACTIVE_STATUSES = (Booking.Status.BOOKED, Booking.Status.PAYMENT_REVIEW, Booking.Status.PAYMENT_PENDING)


class MoMoError(Exception):
    pass


def momo_configured():
    required = ("MTN_MOMO_SUBSCRIPTION_KEY", "MTN_MOMO_API_USER", "MTN_MOMO_API_KEY")
    return all(os.environ.get(key) for key in required)


def _momo_request(method, path, *, payload=None, reference_id=None):
    base_url = os.environ.get("MTN_MOMO_BASE_URL", "https://sandbox.momodeveloper.mtn.com").rstrip("/")
    target = os.environ.get("MTN_MOMO_TARGET_ENVIRONMENT", "sandbox")
    api_user = os.environ["MTN_MOMO_API_USER"]
    api_key = os.environ["MTN_MOMO_API_KEY"]
    subscription_key = os.environ["MTN_MOMO_SUBSCRIPTION_KEY"]
    credentials = base64.b64encode(f"{api_user}:{api_key}".encode()).decode()
    token_request = Request(
        f"{base_url}/collection/token/",
        data=b"",
        headers={"Authorization": f"Basic {credentials}", "Ocp-Apim-Subscription-Key": subscription_key},
        method="POST",
    )
    try:
        with urlopen(token_request, timeout=15) as response:
            token_data = json.loads(response.read().decode())
        token = token_data["access_token"]
        headers = {
            "Authorization": f"Bearer {token}",
            "Ocp-Apim-Subscription-Key": subscription_key,
            "X-Target-Environment": target,
            "Content-Type": "application/json",
        }
        if method == "POST":
            headers["X-Reference-Id"] = str(reference_id)
            callback_url = os.environ.get("MTN_MOMO_CALLBACK_URL")
            if callback_url:
                headers["X-Callback-Url"] = callback_url
        request = Request(
            f"{base_url}{path}",
            data=json.dumps(payload).encode() if payload is not None else None,
            headers=headers,
            method=method,
        )
        with urlopen(request, timeout=20) as response:
            body = response.read().decode()
            return response.status, json.loads(body) if body else {}
    except (HTTPError, URLError, TimeoutError, KeyError, ValueError) as exc:
        body = ""
        if isinstance(exc, HTTPError):
            body = exc.read().decode(errors="replace")[:300]
        raise MoMoError(f"MTN MoMo request failed. {body or str(exc)}") from exc


def request_momo_payment(*, booking, phone_number):
    if not momo_configured():
        raise MoMoError("MTN MoMo credentials are not configured yet.")
    if booking.currency_code != "RWF":
        raise MoMoError("Set this listing’s currency to RWF before accepting MTN MoMo payments.")
    attempt = MoMoPayment.objects.create(
        booking=booking,
        external_id=f"ijuru-booking-{booking.pk}-{uuid.uuid4().hex[:12]}",
        payer_number=phone_number,
    )
    try:
        status, _ = _momo_request(
            "POST",
            "/collection/v1_0/requesttopay",
            reference_id=attempt.reference_id,
            payload={
                "amount": format(booking.amount_due, "f"),
                "currency": booking.currency_code,
                "externalId": attempt.external_id,
                "payer": {"partyIdType": "MSISDN", "partyId": phone_number},
                "payerMessage": f"Ijuru Hub booking {booking.pk}",
                "payeeNote": f"Booking {booking.pk}",
            },
        )
    except MoMoError as exc:
        attempt.status = MoMoPayment.Status.FAILED
        attempt.provider_reason = str(exc)[:255]
        attempt.save(update_fields=["status", "provider_reason", "updated_at"])
        raise
    if status != 202:
        attempt.status = MoMoPayment.Status.FAILED
        attempt.provider_reason = f"Unexpected MTN response: {status}"[:255]
        attempt.save(update_fields=["status", "provider_reason", "updated_at"])
        raise MoMoError("MTN MoMo did not accept the payment request.")
    return attempt


@transaction.atomic
def refresh_momo_payment(*, reference_id):
    attempt = MoMoPayment.objects.select_related("booking__listing").select_for_update().get(reference_id=reference_id)
    status_code, data = _momo_request(
        "GET", f"/collection/v1_0/requesttopay/{quote(str(attempt.reference_id))}"
    )
    if status_code != 200:
        raise MoMoError("Could not verify the payment with MTN MoMo.")
    provider_status = data.get("status", "").upper()
    if provider_status == "SUCCESSFUL":
        # Validate provider-reported transaction details before confirming the booking.
        try:
            amount_matches = Decimal(str(data.get("amount"))) == attempt.booking.amount_due
        except Exception:
            amount_matches = False
        if (
            not amount_matches
            or data.get("currency") != attempt.booking.currency_code
            or data.get("externalId") != attempt.external_id
        ):
            raise MoMoError("MTN payment details do not match this booking; it needs staff review.")
        attempt.status = MoMoPayment.Status.SUCCESSFUL
        attempt.financial_transaction_id = str(data.get("financialTransactionId", ""))[:100]
        attempt.provider_reason = "Verified by MTN MoMo"
        attempt.save(update_fields=["status", "financial_transaction_id", "provider_reason", "updated_at"])
        booking = attempt.booking
        if booking.status == Booking.Status.PAYMENT_PENDING:
            occupied = overlapping_active_bookings(
                booking.listing, booking.starts_on, booking.ends_on,
                exclude_id=booking.pk,
            ).count()
            if occupied < booking.listing.quantity:
                booking.status = Booking.Status.BOOKED
                booking.reviewed_at = timezone.now()
                booking.save(update_fields=["status", "reviewed_at", "ends_on"])
                notify_user(
                    user=booking.customer,
                    title="Your booking is confirmed",
                    message=f"MTN MoMo payment was received for {booking.listing.name} (booking #{booking.pk}).",
                    category="payment",
                    target_url=reverse("coworking:booking_detail", args=[booking.pk]),
                    dedupe_key=f"booking-{booking.pk}-confirmed",
                )
            else:
                booking.status = Booking.Status.PAYMENT_ISSUE
                booking.review_note = "MTN confirmed payment after the one-hour hold, but this space is no longer available. Contact the customer to arrange next steps/refund."
                booking.save(update_fields=["status", "review_note", "ends_on"])
                notify_user(
                    user=booking.customer,
                    title="Your payment needs follow-up",
                    message=f"MTN received payment for booking #{booking.pk}, but the space is no longer available. Ijuru Hub staff will contact you.",
                    category="payment",
                    target_url=reverse("coworking:booking_detail", args=[booking.pk]),
                    dedupe_key=f"booking-{booking.pk}-payment-issue",
                )
                notify_staff(
                    title="Successful payment needs follow-up",
                    message=f"Booking #{booking.pk} was paid after its hold expired and the space is no longer available.",
                    category="payment",
                    target_url=reverse("coworking:staff_bookings") + f"?q={booking.pk}",
                    dedupe_key=f"booking-{booking.pk}-payment-issue",
                )
    elif provider_status in {"FAILED", "REJECTED"}:
        attempt.status = MoMoPayment.Status.FAILED
        attempt.provider_reason = str(data.get("reason", provider_status))[:255]
        attempt.save(update_fields=["status", "provider_reason", "updated_at"])
        if attempt.booking.status == Booking.Status.PAYMENT_PENDING:
            attempt.booking.status = Booking.Status.REJECTED
            attempt.booking.review_note = "MTN MoMo payment was not completed."
            attempt.booking.save(update_fields=["status", "review_note", "ends_on"])
            notify_user(
                user=attempt.booking.customer,
                title="MTN MoMo payment was not completed",
                message=f"Payment for booking #{attempt.booking.pk} failed or was declined. The space hold has been released.",
                category="payment",
                target_url=reverse("coworking:booking_detail", args=[attempt.booking.pk]),
                dedupe_key=f"booking-{attempt.booking.pk}-momo-failed",
            )
    return attempt


def overlapping_active_bookings(listing, starts_on, ends_on, *, exclude_id=None, now=None):
    now = now or timezone.now()
    queryset = Booking.objects.filter(
        listing=listing,
        starts_on__lte=ends_on,
        ends_on__gte=starts_on,
    ).filter(
        Q(status=Booking.Status.BOOKED)
        | Q(status=Booking.Status.PAYMENT_REVIEW, submitted_at__gt=now - timedelta(hours=1))
        | Q(status=Booking.Status.PAYMENT_PENDING, submitted_at__gt=now - timedelta(hours=1))
    )
    if exclude_id is not None:
        queryset = queryset.exclude(pk=exclude_id)
    return queryset


def available_quantity(listing, starts_on, period, *, now=None):
    ends_on = end_date_for_period(starts_on, period)
    occupied = overlapping_active_bookings(listing, starts_on, ends_on, now=now).count()
    return max(0, listing.quantity - occupied)


@transaction.atomic
def submit_booking(*, listing_id, customer, period, starts_on, payment_reference=""):
    """Create a one-unit hold; locking the listing serializes competing requests."""
    listing = SpaceListing.objects.select_for_update().get(pk=listing_id, is_active=True)
    ends_on = end_date_for_period(starts_on, period)
    now = timezone.now()
    occupied = overlapping_active_bookings(listing, starts_on, ends_on, now=now).count()
    if occupied >= listing.quantity:
        raise ValidationError("Sorry, this listing has no availability for those dates.")
    if starts_on < timezone.localdate():
        raise ValidationError("Choose today or a future start date.")
    return Booking.objects.create(
        listing=listing,
        customer=customer,
        period=period,
        starts_on=starts_on,
        amount_due=listing.price_for(period),
        currency_code=listing.currency_code,
        payment_reference=payment_reference,
        submitted_at=now,
    )


@transaction.atomic
def approve_payment(*, booking_id, staff_user, review_note=""):
    booking = Booking.objects.select_related("listing").select_for_update().get(pk=booking_id)
    listing = SpaceListing.objects.select_for_update().get(pk=booking.listing_id)
    if booking.status != Booking.Status.PAYMENT_REVIEW:
        raise ValidationError("Only bookings awaiting payment review can be approved.")
    occupied = overlapping_active_bookings(
        listing,
        booking.starts_on,
        booking.ends_on,
        exclude_id=booking.pk,
    ).count()
    if occupied >= listing.quantity:
        raise ValidationError("The hold expired and this space is no longer available for those dates.")
    booking.status = Booking.Status.BOOKED
    booking.review_note = review_note
    booking.reviewed_at = timezone.now()
    booking.reviewed_by = staff_user
    booking.save(update_fields=["status", "review_note", "reviewed_at", "reviewed_by", "ends_on"])
    notify_user(
        user=booking.customer,
        title="Your booking is confirmed",
        message=f"Payment was approved for {booking.listing.name} (booking #{booking.pk}).",
        category="payment",
        target_url=reverse("coworking:booking_detail", args=[booking.pk]),
        dedupe_key=f"booking-{booking.pk}-confirmed",
    )
    return booking


@transaction.atomic
def reject_payment(*, booking_id, staff_user, review_note=""):
    booking = Booking.objects.select_for_update().get(pk=booking_id)
    if booking.status != Booking.Status.PAYMENT_REVIEW:
        raise ValidationError("Only bookings awaiting payment review can be rejected.")
    booking.status = Booking.Status.REJECTED
    booking.review_note = review_note
    booking.reviewed_at = timezone.now()
    booking.reviewed_by = staff_user
    booking.save(update_fields=["status", "review_note", "reviewed_at", "reviewed_by", "ends_on"])
    notify_user(
        user=booking.customer,
        title="Payment was not approved",
        message=f"Staff could not verify payment for booking #{booking.pk}. Contact Ijuru Hub if you need help.",
        category="payment",
        target_url=reverse("coworking:booking_detail", args=[booking.pk]),
        dedupe_key=f"booking-{booking.pk}-payment-rejected",
    )
    return booking
