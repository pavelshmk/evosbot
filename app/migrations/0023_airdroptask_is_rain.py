# Generated by Django 2.2.2 on 2020-06-29 16:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0022_airdroptask'),
    ]

    operations = [
        migrations.AddField(
            model_name='airdroptask',
            name='is_rain',
            field=models.BooleanField(default=False),
        ),
    ]
