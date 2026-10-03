from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("coworking", "0007_communitypost_media"),
    ]

    operations = [
        migrations.AlterField(
            model_name="communitypost",
            name="category",
            field=models.CharField(
                choices=[("post", "Post"), ("event", "Event"), ("promotion", "Promotion"), ("job", "Job offer")],
                max_length=12,
            ),
        ),
    ]
