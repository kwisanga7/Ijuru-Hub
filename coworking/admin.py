from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import Booking, MoMoPayment, SpaceListing
from .services import approve_payment, reject_payment


@admin.register(SpaceListing)
class SpaceListingAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "quantity", "currency_code", "daily_price", "weekly_price", "monthly_price", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "listing", "customer", "period", "starts_on", "ends_on", "payment_queue_status", "submitted_at")
    list_filter = ("status", "period", "listing__category")
    search_fields = ("customer__username", "customer__email", "listing__name", "payment_reference")
    readonly_fields = ("listing", "customer", "period", "starts_on", "ends_on", "status", "amount_due", "currency_code", "payment_reference", "review_note", "qr_token", "submitted_at", "reviewed_at", "reviewed_by", "checked_in_at", "checked_out_at")
    actions = ("approve_selected_payments", "reject_selected_payments")

    @admin.display(description="Payment / booking status")
    def payment_queue_status(self, booking):
        if booking.status == Booking.Status.PAYMENT_REVIEW and not booking.payment_review_hold_active:
            return "Hold expired — review availability before approval"
        return booking.get_status_display()

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Approve payment and confirm booking")
    def approve_selected_payments(self, request, queryset):
        for booking in queryset:
            try:
                approve_payment(booking_id=booking.pk, staff_user=request.user)
            except ValidationError as exc:
                self.message_user(request, f"Booking {booking.pk}: {exc}", level=messages.ERROR)
            else:
                self.message_user(request, f"Booking {booking.pk} confirmed.", level=messages.SUCCESS)

    @admin.action(description="Reject payment and release held space")
    def reject_selected_payments(self, request, queryset):
        for booking in queryset:
            try:
                reject_payment(booking_id=booking.pk, staff_user=request.user)
            except ValidationError as exc:
                self.message_user(request, f"Booking {booking.pk}: {exc}", level=messages.ERROR)
            else:
                self.message_user(request, f"Booking {booking.pk} rejected.", level=messages.WARNING)


@admin.register(MoMoPayment)
class MoMoPaymentAdmin(admin.ModelAdmin):
    list_display = ("booking", "status", "payer_number", "reference_id", "financial_transaction_id", "created_at")
    list_filter = ("status",)
    search_fields = ("booking__customer__username", "booking__customer__email", "reference_id", "external_id", "financial_transaction_id")
    readonly_fields = tuple(field.name for field in MoMoPayment._meta.fields)
