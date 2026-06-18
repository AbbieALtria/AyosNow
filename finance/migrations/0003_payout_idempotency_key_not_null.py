from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0002_payout_idempotency_key_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="payout",
            name="idempotency_key",
            field=models.CharField(max_length=160, unique=True),
        ),
    ]
