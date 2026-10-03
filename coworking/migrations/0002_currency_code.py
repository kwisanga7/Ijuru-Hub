from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("coworking", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="spacelisting",
            name="currency_code",
            field=models.CharField(blank=True, help_text="Enter the client-approved currency code, for example RWF.", max_length=3),
        ),
        migrations.AddField(
            model_name="booking",
            name="currency_code",
            field=models.CharField(blank=True, max_length=3),
        ),
    ]
