from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def create_existing_profiles(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    MemberProfile = apps.get_model("coworking", "MemberProfile")
    MemberProfile.objects.using(schema_editor.connection.alias).bulk_create(
        [MemberProfile(user_id=user_id) for user_id in User.objects.using(schema_editor.connection.alias).values_list("pk", flat=True)],
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("coworking", "0004_notification"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MemberProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("display_name", models.CharField(blank=True, max_length=120)),
                ("job_title", models.CharField(blank=True, max_length=120)),
                ("company", models.CharField(blank=True, max_length=140)),
                ("bio", models.TextField(blank=True, max_length=700)),
                ("website", models.URLField(blank=True, max_length=200)),
                ("public_email", models.EmailField(blank=True, max_length=254)),
                ("show_email", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="member_profile", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.RunPython(create_existing_profiles, migrations.RunPython.noop),
        migrations.CreateModel(
            name="CommunityPost",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("category", models.CharField(choices=[("event", "Event"), ("promotion", "Promotion"), ("job", "Job offer")], max_length=12)),
                ("title", models.CharField(max_length=120)),
                ("body", models.TextField(max_length=1800)),
                ("event_date", models.DateTimeField(blank=True, help_text="For events, enter the date and time.", null=True)),
                ("status", models.CharField(choices=[("pending", "Pending review"), ("approved", "Published"), ("rejected", "Not approved")], db_index=True, default="pending", max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="community_posts", to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_community_posts", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
