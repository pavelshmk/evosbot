# Generated by Django 2.2.2 on 2019-10-25 21:27

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0010_auto_20190912_0016'),
    ]

    operations = [
        migrations.CreateModel(
            name='UpdateRoleTask',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('remove_roles', models.TextField(null=True)),
                ('add_roles', models.TextField(null=True)),
                ('processed', models.BooleanField(db_index=True, default=False)),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.ServerMember')),
            ],
        ),
    ]