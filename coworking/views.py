import json

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.dateparse import parse_date
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, HttpResponseForbidden
from django.urls import reverse
from urllib.parse import urlencode
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import qrcode
from io import BytesIO

from .forms import BookingRequestForm, CommunityPostForm, CustomerRegistrationForm, MemberProfileForm, SpaceListingForm, StaffAccountCreationForm
from .models import Booking, CommunityPost, MemberProfile, MoMoPayment, Notification, SpaceListing
from .notifications import mark_read as mark_notification_read
from .notifications import notify_staff, notify_user
from .services import MoMoError, approve_payment, available_quantity, momo_configured, refresh_momo_payment, reject_payment, request_momo_payment, submit_booking


def home(request):
    featured_spaces = SpaceListing.objects.filter(is_active=True)[:3]
    today = timezone.localdate()
    for listing in featured_spaces:
        listing.available_quantity = available_quantity(listing, today, Booking.Period.DAY)
    posts = CommunityPost.objects.filter(status=CommunityPost.Status.APPROVED).select_related("author", "author__member_profile")[:6]
    return render(request, "coworking/home.html", {"featured_spaces": featured_spaces, "community_posts": posts})


@login_required
def profile_edit(request):
    profile, _ = MemberProfile.objects.get_or_create(user=request.user)
    form = MemberProfileForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your member profile has been saved.")
        return redirect("coworking:profile_card")
    return render(request, "coworking/profile_edit.html", {"form": form})


def member_profile(request, username):
    member = get_object_or_404(User.objects.select_related("member_profile"), username=username, is_active=True)
    profile, _ = MemberProfile.objects.get_or_create(user=member)
    if not profile.display_name:
        profile.display_name = member.get_full_name() or member.username
    return render(request, "coworking/member_profile.html", {"member": member, "profile": profile})


@login_required
def profile_card(request):
    profile, _ = MemberProfile.objects.get_or_create(user=request.user)
    if not profile.display_name:
        profile.display_name = request.user.get_full_name() or request.user.username
    return render(request, "coworking/profile_card.html", {"profile": profile})


def profile_qr(request, username):
    member = get_object_or_404(User, username=username, is_active=True)
    target = request.build_absolute_uri(reverse("coworking:member_profile", args=[member.username]))
    image = qrcode.make(target)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return HttpResponse(buffer.getvalue(), content_type="image/png")


@login_required
def community_post_create(request):
    form = CommunityPostForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.category = CommunityPost.Category.POST
        post.title = post.body.splitlines()[0][:120] or "Community post"
        post.event_date = None
        post.status = CommunityPost.Status.APPROVED
        post.save()
        messages.success(request, "Your post is now visible on the community board.")
        return redirect("coworking:home")
    return render(request, "coworking/community_post_form.html", {"form": form})


@staff_member_required
def staff_community_posts(request):
    posts = CommunityPost.objects.select_related("author", "reviewed_by")
    return render(request, "coworking/staff_community_posts.html", {"posts": posts})


@staff_member_required
@require_POST
def staff_community_post_review(request, pk, action):
    post = get_object_or_404(CommunityPost, pk=pk)
    if action == "delete":
        title = post.title
        post.delete()
        messages.success(request, f"Post ‘{title}’ deleted.")
    elif action == "publish":
        post.status = CommunityPost.Status.APPROVED
        post.reviewed_at = timezone.now()
        post.reviewed_by = request.user
        post.save(update_fields=["status", "reviewed_at", "reviewed_by"])
        messages.success(request, "Post published.")
    elif action == "hide":
        post.status = CommunityPost.Status.REJECTED
        post.reviewed_at = timezone.now()
        post.reviewed_by = request.user
        post.save(update_fields=["status", "reviewed_at", "reviewed_by"])
        messages.success(request, "Post hidden from the community board.")
    else:
        messages.error(request, "Unknown post management action.")
    return redirect("coworking:staff_community_posts")


def listing_list(request):
    listings = SpaceListing.objects.filter(is_active=True)
    category = request.GET.get("category", "")
    period = request.GET.get("period", Booking.Period.DAY)
    if period not in Booking.Period.values:
        period = Booking.Period.DAY
    starts_on = parse_date(request.GET.get("starts_on", "")) or timezone.localdate()
    if category:
        listings = listings.filter(category=category)
    for listing in listings:
        listing.available_quantity = available_quantity(listing, starts_on, period)
    return render(request, "coworking/listing_list.html", {
        "listings": listings,
        "categories": SpaceListing.Category.choices,
        "selected_category": category,
        "selected_period": period,
        "selected_start_date": starts_on,
        "booking_periods": Booking.Period.choices,
    })


def listing_detail(request, slug):
    listing = get_object_or_404(SpaceListing, slug=slug, is_active=True)
    period = request.GET.get("period", Booking.Period.DAY)
    if period not in Booking.Period.values:
        period = Booking.Period.DAY
    starts_on = parse_date(request.GET.get("starts_on", "")) or timezone.localdate()
    return render(request, "coworking/listing_detail.html", {
        "listing": listing,
        "available_quantity": available_quantity(listing, starts_on, period),
        "selected_period": period,
        "selected_start_date": starts_on,
        "booking_periods": Booking.Period.choices,
        "booking_path": f"{reverse('coworking:booking_create', args=[listing.slug])}?{urlencode({'period': period, 'starts_on': starts_on.isoformat()})}",
    })


def register(request):
    if request.user.is_authenticated:
        return redirect("coworking:listing_list")
    form = CustomerRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, "Your Ijuru Hub account is ready.")
        return redirect("coworking:listing_list")
    return render(request, "coworking/register.html", {"form": form})


@login_required
def booking_create(request, slug):
    listing = get_object_or_404(SpaceListing, slug=slug, is_active=True)
    initial = {
        "period": request.GET.get("period", Booking.Period.DAY),
        "starts_on": request.GET.get("starts_on", timezone.localdate()),
    }
    form = BookingRequestForm(request.POST or None, initial=initial)
    use_momo = momo_configured()
    if use_momo:
        form.fields.pop("payment_reference", None)
        if listing.currency_code != "RWF":
            form.add_error(None, "MTN MoMo checkout requires this listing to have its price and currency set to RWF. Please contact Ijuru Hub staff.")
    else:
        form.fields.pop("momo_phone_number", None)
    if request.method == "POST" and use_momo and not form.data.get("momo_phone_number", "").strip():
        form.add_error("momo_phone_number", "Enter the MTN MoMo number to receive the payment request.")
    if request.method == "POST" and form.is_valid():
        try:
            booking = submit_booking(
                listing_id=listing.pk,
                customer=request.user,
                period=form.cleaned_data["period"],
                starts_on=form.cleaned_data["starts_on"],
                payment_reference=form.cleaned_data.get("payment_reference", ""),
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            if use_momo:
                booking.status = Booking.Status.PAYMENT_PENDING
                booking.save(update_fields=["status", "ends_on"])
                try:
                    request_momo_payment(booking=booking, phone_number=form.cleaned_data["momo_phone_number"])
                except MoMoError as exc:
                    booking.status = Booking.Status.PAYMENT_REVIEW
                    booking.review_note = f"MoMo request could not be started: {exc}"[:1000]
                    booking.save(update_fields=["status", "review_note", "ends_on"])
                    notify_user(
                        user=request.user,
                        title="MoMo request could not start",
                        message=f"Booking #{booking.pk} is held for one hour. Staff can help you complete payment.",
                        category=Notification.Category.PAYMENT,
                        target_url=reverse("coworking:booking_detail", args=[booking.pk]),
                        dedupe_key=f"booking-{booking.pk}-momo-start-failed",
                    )
                    notify_staff(
                        title="MoMo payment request failed",
                        message=f"Booking #{booking.pk} needs manual payment follow-up.",
                        category=Notification.Category.PAYMENT,
                        target_url=reverse("coworking:staff_bookings") + f"?q={booking.pk}",
                        dedupe_key=f"booking-{booking.pk}-momo-start-failed",
                    )
                    messages.error(request, "We could not start the MTN MoMo request. Your one-hour hold remains active; staff can review the payment manually.")
                    return redirect("coworking:booking_detail", pk=booking.pk)
                notify_user(
                    user=request.user,
                    title="Approve your MTN MoMo payment",
                    message=f"Approve the payment request for booking #{booking.pk} on your phone. Your space is held for one hour.",
                    category=Notification.Category.PAYMENT,
                    target_url=reverse("coworking:booking_detail", args=[booking.pk]),
                    dedupe_key=f"booking-{booking.pk}-momo-requested",
                )
                notify_staff(
                    title="New MoMo booking request",
                    message=f"Booking #{booking.pk} is waiting for the customer to approve payment.",
                    category=Notification.Category.BOOKING,
                    target_url=reverse("coworking:staff_bookings") + f"?q={booking.pk}",
                    dedupe_key=f"booking-{booking.pk}-submitted",
                )
                messages.info(request, "An MTN MoMo payment request has been sent. Approve it on your phone; your booking will confirm automatically after MTN verifies payment.")
                return redirect("coworking:booking_detail", pk=booking.pk)
            messages.info(
                request,
                "Your one-hour space hold has started. Complete payment using the method arranged with Ijuru Hub, then allow staff to verify it.",
            )
            notify_user(
                user=request.user,
                title="Booking request received",
                message=f"Booking #{booking.pk} is held for one hour while Ijuru Hub reviews your payment.",
                category=Notification.Category.BOOKING,
                target_url=reverse("coworking:booking_detail", args=[booking.pk]),
                dedupe_key=f"booking-{booking.pk}-manual-submitted-customer",
            )
            notify_staff(
                title="Payment needs review",
                message=f"Booking #{booking.pk} is awaiting payment review.",
                category=Notification.Category.PAYMENT,
                target_url=reverse("coworking:staff_bookings") + f"?q={booking.pk}",
                dedupe_key=f"booking-{booking.pk}-submitted",
            )
            return redirect("coworking:booking_detail", pk=booking.pk)
    return render(request, "coworking/booking_form.html", {"form": form, "listing": listing, "momo_enabled": use_momo})


@login_required
def booking_detail(request, pk):
    booking = get_object_or_404(Booking.objects.select_related("listing", "customer"), pk=pk)
    if not (request.user == booking.customer or request.user.is_staff):
        return redirect("coworking:my_bookings")
    if booking.status == Booking.Status.PAYMENT_PENDING and momo_configured():
        try:
            payment = booking.momo_payment
            refresh_momo_payment(reference_id=payment.reference_id)
            booking.refresh_from_db()
        except (MoMoPayment.DoesNotExist, MoMoError):
            pass
    remaining = max(0, int((booking.payment_review_expires_at - timezone.now()).total_seconds()))
    return render(request, "coworking/booking_detail.html", {"booking": booking, "hold_seconds_remaining": remaining})


@csrf_exempt
def momo_callback(request):
    """Treat MTN callback as a signal only; fetch and verify status server-to-server."""
    if request.method not in {"POST", "PUT"}:
        return HttpResponse(status=405)
    try:
        payload = json.loads(request.body.decode("utf-8"))
        reference_id = payload.get("referenceId") or payload.get("reference_id")
        if not reference_id:
            return HttpResponse(status=400)
        refresh_momo_payment(reference_id=reference_id)
    except (ValueError, KeyError, MoMoPayment.DoesNotExist, MoMoError):
        return HttpResponse(status=400)
    return HttpResponse(status=200)


@login_required
def my_bookings(request):
    bookings = Booking.objects.filter(customer=request.user).select_related("listing")
    return render(request, "coworking/my_bookings.html", {"bookings": bookings})


@login_required
def booking_qr(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if not (request.user == booking.customer or request.user.is_staff):
        return HttpResponseForbidden()
    if booking.status != Booking.Status.BOOKED:
        return HttpResponseForbidden("A QR check-in code is issued after the booking is confirmed.")
    target = request.build_absolute_uri(reverse("coworking:staff_check_in", args=[booking.qr_token]))
    image = qrcode.make(target)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return HttpResponse(buffer.getvalue(), content_type="image/png")


@staff_member_required
def staff_check_in(request, token):
    booking = get_object_or_404(Booking.objects.select_related("listing", "customer"), qr_token=token)
    if booking.status != Booking.Status.BOOKED:
        messages.error(request, "This booking is not confirmed.")
        return redirect("coworking:booking_detail", pk=booking.pk)
    if not (booking.starts_on <= timezone.localdate() <= booking.ends_on):
        messages.error(request, "This booking is not valid for check-in today.")
        return redirect("coworking:booking_detail", pk=booking.pk)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "check_in" and not booking.checked_in_at:
            booking.checked_in_at = timezone.now()
            booking.save(update_fields=["checked_in_at", "ends_on"])
            messages.success(request, "Check-in recorded.")
            notify_user(
                user=booking.customer,
                title="You are checked in",
                message=f"Your visit to {booking.listing.name} has started.",
                category=Notification.Category.VISIT,
                target_url=reverse("coworking:booking_detail", args=[booking.pk]),
                dedupe_key=f"booking-{booking.pk}-checked-in",
            )
        elif action == "check_out" and booking.checked_in_at and not booking.checked_out_at:
            booking.checked_out_at = timezone.now()
            booking.save(update_fields=["checked_out_at", "ends_on"])
            messages.success(request, "Check-out recorded.")
            notify_user(
                user=booking.customer,
                title="You are checked out",
                message=f"Your visit to {booking.listing.name} is complete.",
                category=Notification.Category.VISIT,
                target_url=reverse("coworking:booking_detail", args=[booking.pk]),
                dedupe_key=f"booking-{booking.pk}-checked-out",
            )
        else:
            messages.error(request, "That check-in action is not available for this booking.")
    return render(request, "coworking/staff_check_in.html", {"booking": booking})


@staff_member_required
def staff_dashboard(request):
    today = timezone.localdate()
    active_listings = SpaceListing.objects.filter(is_active=True)
    available_today = sum(
        available_quantity(listing, today, Booking.Period.DAY)
        for listing in active_listings
    )
    payment_queue = (
        Booking.objects.filter(status=Booking.Status.PAYMENT_REVIEW)
        .select_related("listing", "customer")
        .order_by("submitted_at")
    )
    upcoming = (
        Booking.objects.filter(
            status=Booking.Status.BOOKED,
            ends_on__gte=today,
        )
        .select_related("listing", "customer")
        .order_by("starts_on")[:8]
    )
    today_visits = Booking.objects.filter(
        status=Booking.Status.BOOKED,
        checked_in_at__date=today,
    ).count()
    context = {
        "active_listing_count": active_listings.count(),
        "available_today": available_today,
        "payment_queue": payment_queue[:12],
        "payment_queue_count": payment_queue.count(),
        "upcoming_bookings": upcoming,
        "today_visits": today_visits,
        "today": today,
        "momo_pending": Booking.objects.filter(status=Booking.Status.PAYMENT_PENDING).select_related("listing", "customer").order_by("submitted_at")[:8],
        "payment_issues": Booking.objects.filter(status=Booking.Status.PAYMENT_ISSUE).select_related("listing", "customer").order_by("-submitted_at")[:8],
    }
    return render(request, "coworking/staff_dashboard.html", context)


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user)
    page = Paginator(notifications, 25).get_page(request.GET.get("page"))
    return render(request, "coworking/notification_list.html", {"page": page})


@login_required
def notification_open(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    mark_notification_read(notification)
    destination = notification.target_url
    if destination.startswith("/") and not destination.startswith("//"):
        return redirect(destination)
    return redirect("coworking:notification_list")


@login_required
@require_POST
def notification_mark_all_read(request):
    Notification.objects.filter(user=request.user, read_at__isnull=True).update(read_at=timezone.now())
    messages.success(request, "All notifications marked as read.")
    return redirect("coworking:notification_list")


@staff_member_required
def staff_spaces(request):
    spaces = SpaceListing.objects.all()
    query = request.GET.get("q", "").strip()
    if query:
        spaces = spaces.filter(Q(name__icontains=query) | Q(description__icontains=query))
    return render(request, "coworking/staff_spaces.html", {"spaces": spaces, "query": query})


@staff_member_required
def staff_space_edit(request, pk=None):
    listing = get_object_or_404(SpaceListing, pk=pk) if pk else None
    form = SpaceListingForm(request.POST or None, request.FILES or None, instance=listing)
    if request.method == "POST" and form.is_valid():
        listing = form.save()
        messages.success(request, f"{listing.name} saved.")
        return redirect("coworking:staff_spaces")
    return render(request, "coworking/staff_space_form.html", {"form": form, "listing": listing})


@staff_member_required
def staff_bookings(request):
    bookings = Booking.objects.select_related("listing", "customer", "momo_payment")
    status = request.GET.get("status", "")
    query = request.GET.get("q", "").strip()
    valid_statuses = {value for value, _label in Booking.Status.choices}
    if status in valid_statuses:
        bookings = bookings.filter(status=status)
    else:
        status = ""
    if query:
        search_filter = (
            Q(customer__username__icontains=query)
            | Q(customer__email__icontains=query)
            | Q(customer__first_name__icontains=query)
            | Q(customer__last_name__icontains=query)
            | Q(listing__name__icontains=query)
            | Q(payment_reference__icontains=query)
        )
        if query.isdigit():
            search_filter |= Q(pk=int(query))
        bookings = bookings.filter(search_filter)
    page = Paginator(bookings, 20).get_page(request.GET.get("page"))
    return render(request, "coworking/staff_bookings.html", {
        "page": page, "status": status, "query": query, "statuses": Booking.Status.choices,
        "today": timezone.localdate(),
    })


@staff_member_required
def staff_people(request):
    query = request.GET.get("q", "").strip()
    people = User.objects.order_by("-date_joined")
    if query:
        people = people.filter(
            Q(username__icontains=query) | Q(email__icontains=query)
            | Q(first_name__icontains=query) | Q(last_name__icontains=query)
        )
    page = Paginator(people, 30).get_page(request.GET.get("page"))
    staff_form = StaffAccountCreationForm()
    return render(request, "coworking/staff_people.html", {
        "page": page, "query": query, "staff_form": staff_form,
        "can_manage_staff": request.user.is_superuser,
        "current_user_id": request.user.pk,
    })


@staff_member_required
@require_POST
def staff_create_account(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden()
    form = StaffAccountCreationForm(request.POST)
    if form.is_valid():
        user = form.save()
        messages.success(request, f"Staff account for {user.username} created.")
    else:
        messages.error(request, f"Could not create staff account: {form.errors.as_text()}")
    return redirect("coworking:staff_people")


@staff_member_required
@require_POST
def staff_toggle_account(request, pk):
    if not request.user.is_superuser:
        return HttpResponseForbidden()
    account = get_object_or_404(User, pk=pk)
    if account.pk == request.user.pk or account.is_superuser:
        messages.error(request, "You cannot disable your own account or another superuser here.")
    else:
        account.is_active = not account.is_active
        account.save(update_fields=["is_active"])
        messages.success(request, f"{account.username} account is now {'active' if account.is_active else 'disabled'}.")
    return redirect("coworking:staff_people")


@staff_member_required
@require_POST
def staff_booking_review(request, pk, action):
    booking = get_object_or_404(Booking, pk=pk)
    if action == "approve":
        try:
            approve_payment(booking_id=booking.pk, staff_user=request.user)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, f"Booking #{booking.pk} confirmed.")
    elif action == "reject":
        try:
            reject_payment(booking_id=booking.pk, staff_user=request.user)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.warning(request, f"Payment for booking #{booking.pk} rejected; its held space is released.")
    else:
        messages.error(request, "Unknown payment review action.")
    return redirect("coworking:staff_dashboard")
