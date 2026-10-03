from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("coworking", "0008_communitypost_post_category"),
    ]

    operations = [
        migrations.AlterField(
            model_name="communitypost",
            name="body",
            field=models.TextField(max_length=5000),
        ),
    ]
