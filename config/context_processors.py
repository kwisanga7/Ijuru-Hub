import os

from coworking.models import Notification


def authentication_options(request):
    return {
        "google_sign_in_configured": bool(
            os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET")
        )
    }


def notification_summary(request):
    if not request.user.is_authenticated:
        return {"unread_notification_count": 0}
    return {
        "unread_notification_count": Notification.objects.filter(
            user=request.user,
            read_at__isnull=True,
        ).count()
    }
