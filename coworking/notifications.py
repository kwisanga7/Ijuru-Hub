from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Notification


def notify_user(*, user, title, message, category=Notification.Category.BOOKING, target_url="", dedupe_key=None):
    if dedupe_key:
        dedupe_key = f"user-{user.pk}-{dedupe_key}"[:180]
        notification, _created = Notification.objects.get_or_create(
            dedupe_key=dedupe_key,
            defaults={
                "user": user,
                "title": title,
                "message": message,
                "category": category,
                "target_url": target_url,
            },
        )
        return notification
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        category=category,
        target_url=target_url,
    )


def notify_staff(*, title, message, category=Notification.Category.BOOKING, target_url="", dedupe_key=None):
    user_model = get_user_model()
    created = []
    for user in user_model.objects.filter(is_active=True, is_staff=True).iterator():
        key = f"{dedupe_key}-staff-{user.pk}" if dedupe_key else None
        created.append(notify_user(
            user=user,
            title=title,
            message=message,
            category=category,
            target_url=target_url,
            dedupe_key=key,
        ))
    return created


def mark_read(notification):
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
    return notification
