# Generated by Django 2.2.2 on 2019-11-25 16:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0014_servermember_last_forced_activity_update'),
    ]

    operations = [
        migrations.AddField(
            model_name='servermember',
            name='otp_active',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='servermember',
            name='otp_qr_message_id',
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='servermember',
            name='otp_secret',
            field=models.CharField(blank=True, max_length=16, null=True),
        ),
        migrations.AddField(
            model_name='servermember',
            name='otp_threshold',
            field=models.DecimalField(decimal_places=8, default=1, max_digits=32),
        ),
    ]