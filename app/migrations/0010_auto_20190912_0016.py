# Generated by Django 2.2.2 on 2019-09-11 21:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0009_auto_20190909_1655'),
    ]

    operations = [
        migrations.AlterField(
            model_name='servermember',
            name='rank',
            field=models.PositiveSmallIntegerField(choices=[(0, 'Brand new'), (1, 'Newbie'), (2, 'Advanced Member'), (3, 'High-ranker'), (4, 'Professional'), (5, 'Champion'), (6, 'Legend')], default=0),
        ),
    ]