# Generated by Django 2.2.2 on 2020-01-21 18:19

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0018_trackedmasternode'),
    ]

    operations = [
        migrations.RenameField(
            model_name='trackedmasternode',
            old_name='txid',
            new_name='addr',
        ),
    ]