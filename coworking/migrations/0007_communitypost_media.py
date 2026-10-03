from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("coworking", "0006_publish_existing_community_posts"),
    ]

    operations = [
        migrations.AddField(
            model_name="communitypost",
            name="media",
            field=models.FileField(blank=True, upload_to="community/"),
        ),
    ]
