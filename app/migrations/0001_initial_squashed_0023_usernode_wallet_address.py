# Generated by Django 2.2.2 on 2019-07-11 11:56

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Broadcast',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField()),
                ('finished', models.BooleanField(default=False)),
                ('user_list', models.TextField()),
                ('progress', models.PositiveIntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name='ServerInvite',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=64)),
                ('uses', models.PositiveIntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name='ServerMember',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('name', models.TextField()),
                ('xp', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('referrer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='referrals', to='app.ServerMember')),
                ('last_message', models.DateTimeField(blank=True, null=True)),
                ('rank', models.PositiveSmallIntegerField(choices=[(0, 'Brand new'), (1, 'Newbie'), (2, 'Junior'), (3, 'Experienced'), (4, 'Veteran'), (5, 'Guru'), (6, 'Sadhu')], default=0)),
                ('last_dislike', models.DateTimeField(blank=True, null=True)),
                ('last_like', models.DateTimeField(blank=True, null=True)),
                ('_dm_channel', models.BigIntegerField(null=True, verbose_name='DM channel ID')),
                ('_wallet_address', models.CharField(blank=True, db_index=True, max_length=64, null=True, verbose_name='wallet address')),
                ('balance', models.DecimalField(decimal_places=8, default=0, max_digits=32)),
                ('received', models.DecimalField(decimal_places=8, default=0, max_digits=32)),
                ('received_unconfirmed', models.DecimalField(decimal_places=8, default=0, max_digits=32)),
                ('confirmed_referrals', models.PositiveIntegerField(default=0, editable=False)),
                ('_staking_wallet_address', models.CharField(blank=True, db_index=True, max_length=64, null=True, verbose_name='staking wallet address')),
                ('is_staking_pool', models.BooleanField(default=False)),
                ('staking_pool_amount', models.DecimalField(decimal_places=8, default=0, max_digits=32)),
                ('masternode_balance', models.DecimalField(decimal_places=8, default=0, max_digits=32)),
                ('_bitcoin_wallet_address', models.CharField(blank=True, db_index=True, max_length=64, null=True, verbose_name='bitcoin wallet address')),
                ('bitcoin_balance', models.DecimalField(decimal_places=8, default=0, max_digits=32)),
                ('bitcoin_received', models.DecimalField(decimal_places=8, default=0, max_digits=32)),
                ('bitcoin_received_unconfirmed', models.DecimalField(decimal_places=8, default=0, max_digits=32)),
                ('activity_counter', models.BigIntegerField(default=0)),
                ('last_rank_change', models.DateTimeField(auto_now_add=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Unstaking',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=8, max_digits=32)),
                ('fulfilled', models.BooleanField(default=False)),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='unstakings', to='app.ServerMember')),
            ],
        ),
        migrations.CreateModel(
            name='MasternodeWithdraw',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=8, max_digits=32)),
                ('fulfill_at', models.DateTimeField()),
                ('fulfilled', models.BooleanField(default=False)),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mn_withdraws', to='app.ServerMember')),
            ],
        ),
        migrations.CreateModel(
            name='Masternode',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('alias', models.CharField(max_length=64)),
                ('address', models.CharField(help_text='IP:port', max_length=64)),
                ('privkey', models.CharField(max_length=128)),
                ('output_txid', models.CharField(blank=True, max_length=128, null=True)),
                ('output_idx', models.PositiveIntegerField(blank=True, null=True)),
                ('active', models.BooleanField(default=False)),
                ('weight', models.PositiveIntegerField(default=0)),
            ],
            options={
                'ordering': ('weight',),
            },
        ),
        migrations.CreateModel(
            name='TradeOrder',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('is_sell', models.BooleanField()),
                ('amount', models.DecimalField(decimal_places=8, max_digits=32)),
                ('btc_price', models.DecimalField(decimal_places=8, max_digits=32)),
                ('member', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='app.ServerMember')),
            ],
        ),
        migrations.CreateModel(
            name='LotteryTicket',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.PositiveSmallIntegerField()),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='app.ServerMember')),
            ],
        ),
        migrations.CreateModel(
            name='UserNode',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('address', models.TextField()),
                ('privkey', models.TextField()),
                ('output_txid', models.CharField(blank=True, max_length=128, null=True)),
                ('output_idx', models.PositiveIntegerField(blank=True, null=True)),
                ('pending', models.BooleanField(default=True)),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='usernodes', to='app.ServerMember')),
                ('wallet_address', models.CharField(blank=True, db_index=True, max_length=64, null=True)),
            ],
        ),
    ]
