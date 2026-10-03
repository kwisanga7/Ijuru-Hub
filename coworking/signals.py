from allauth.account.signals import user_signed_up
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse

from .notifications import notify_staff
from .models import MemberProfile


@receiver(post_save, sender=get_user_model())
def create_member_profile(sender, instance, created, **kwargs):
    if created:
        MemberProfile.objects.get_or_create(user=instance)


@receiver(user_signed_up)
def notify_staff_of_new_member(request, user, **kwargs):
    notify_staff(
        title="New member registered",
        message=f"{user.get_full_name() or user.username} created an Ijuru Hub account.",
        category="account",
        target_url=reverse("coworking:staff_people"),
        dedupe_key=f"member-{user.pk}-registered",
    )
