from django.db import migrations


def publish_pending_posts(apps, schema_editor):
    CommunityPost = apps.get_model("coworking", "CommunityPost")
    CommunityPost.objects.using(schema_editor.connection.alias).filter(status="pending").update(status="approved")


class Migration(migrations.Migration):
    dependencies = [("coworking", "0005_memberprofile_communitypost")]

    operations = [migrations.RunPython(publish_pending_posts, migrations.RunPython.noop)]
