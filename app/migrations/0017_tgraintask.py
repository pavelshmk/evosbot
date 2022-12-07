# Generated by Django 2.2.2 on 2019-12-12 20:01

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0016_servermember_noinform'),
    ]

    operations = [
        migrations.CreateModel(
            name='TGRainTask',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message_id', models.BigIntegerField(null=True)),
                ('users', models.TextField(default='')),
                ('users_cnt', models.PositiveIntegerField()),
                ('amount', models.DecimalField(decimal_places=8, max_digits=32)),
                ('execute_at', models.DateTimeField()),
                ('finished', models.BooleanField(default=False)),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.ServerMember')),
            ],
        ),
    ]