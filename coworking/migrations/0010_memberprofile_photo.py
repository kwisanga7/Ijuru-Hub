from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("coworking", "0009_communitypost_description_length"),
    ]

    operations = [
        migrations.AddField(
            model_name="memberprofile",
            name="photo",
            field=models.ImageField(blank=True, upload_to="member_profiles/"),
        ),
    ]
