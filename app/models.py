from decimal import Decimal
from uuid import uuid4

from computedfields.models import computed, ComputedFieldsModel
from discord import Member
from django.db import models, transaction
from django.db.models import Sum
from django.utils.timezone import now
from dynamic_preferences.registries import global_preferences_registry
from telegram import User
from telegram.utils.helpers import mention_markdown

from evosbot.utils import client, staking_client, get_api_session, send_discord_message, bitcoin_client, tx_logger, fd

global_preferences = global_preferences_registry.manager()


class ServerMember(ComputedFieldsModel):
    class Rank:
        BRAND_NEW = 0
        NEWBIE = 1
        JUNIOR = 2
        EXPERIENCED = 3
        VETERAN = 4
        GURU = 5
        SADHU = 6

        choices = (
            (BRAND_NEW, 'Brand new'),
            (NEWBIE, 'Newbie'),
            (JUNIOR, 'Advanced Member'),
            (EXPERIENCED, 'High-ranker'),
            (VETERAN, 'Professional'),
            (GURU, 'Champion'),
            (SADHU, 'Legend'),
        )

    id = models.BigAutoField(primary_key=True)  # -10**10 + id = telegram
    name = models.TextField()
    username = models.TextField(null=True, blank=True)
    avatar = models.URLField(null=True, blank=True)
    referrer = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals')
    rank = models.PositiveSmallIntegerField(default=Rank.BRAND_NEW, choices=Rank.choices)
    last_rank_change = models.DateTimeField(null=True, blank=True, auto_now_add=True)
    last_forced_activity_update = models.DateTimeField(null=True, blank=True, auto_now_add=True)
    xp = models.DecimalField(default=0, max_digits=10, decimal_places=2)
    activity_counter = models.BigIntegerField(default=0)
    last_message = models.DateTimeField(null=True, blank=True)
    last_like = models.DateTimeField(null=True, blank=True)
    last_dislike = models.DateTimeField(null=True, blank=True)
    noinform = models.BooleanField(default=False)
    _dm_channel = models.BigIntegerField(verbose_name='DM channel ID', null=True, blank=True)

    _wallet_address = models.CharField(max_length=64, verbose_name='wallet address', null=True, blank=True,
                                       db_index=True)
    balance = models.DecimalField(max_digits=32, decimal_places=8, default=0)
    received = models.DecimalField(max_digits=32, decimal_places=8, default=0)
    received_unconfirmed = models.DecimalField(max_digits=32, decimal_places=8, default=0)

    _staking_wallet_address = models.CharField(max_length=64, verbose_name='staking wallet address', null=True,
                                               blank=True, db_index=True)
    is_staking_pool = models.BooleanField(default=True)
    staking_pool_amount = models.DecimalField(max_digits=32, decimal_places=8, default=0)

    masternode_balance = models.DecimalField(max_digits=32, decimal_places=8, default=0)

    _bitcoin_wallet_address = models.CharField(max_length=64, verbose_name='bitcoin wallet address', null=True,
                                               blank=True, db_index=True)
    bitcoin_balance = models.DecimalField(max_digits=32, decimal_places=8, default=0)
    bitcoin_received = models.DecimalField(max_digits=32, decimal_places=8, default=0)
    bitcoin_received_unconfirmed = models.DecimalField(max_digits=32, decimal_places=8, default=0)

    otp_active = models.BooleanField(default=False)
    otp_secret = models.CharField(max_length=16, null=True, blank=True)
    otp_threshold = models.DecimalField(max_digits=32, decimal_places=8, default=1)
    otp_qr_message_id = models.BigIntegerField(null=True, blank=True)

    def __str__(self):
        return '{} (#{})'.format(self.name, self.id)

    @computed(models.PositiveIntegerField(default=0), depends=['referrals#rank'])
    def confirmed_referrals(self):
        return self.referrals.filter(rank__gt=ServerMember.Rank.BRAND_NEW).count()

    @staticmethod
    def from_member_with_created(member: Member, **kwargs):
        sm, created = ServerMember.objects.get_or_create(id=member.id, defaults={
            'name': member.display_name,
            'avatar': member.avatar_url,
            **kwargs
        })
        if not created:
            if member.display_name != sm.name:
                sm.name = member.display_name
            if member.avatar_url != sm.avatar:
                sm.avatar = member.avatar_url
            sm.save()
        return sm, created

    @staticmethod
    def from_member(member: Member, **kwargs):
        obj, created = ServerMember.from_member_with_created(member, **kwargs)
        return obj

    @staticmethod
    def from_tg_user_with_created(user: User, **kwargs):
        sm, created = ServerMember.objects.get_or_create(id=-10**10 + user.id, defaults={
            'name': user.full_name,
            'username': user.username,
        })
        if not created:
            if user.full_name != sm.name:
                sm.name = user.full_name
            sm.save()
        return sm, created

    @staticmethod
    def from_tg_user(user: User, **kwargs):
        obj, created = ServerMember.from_tg_user_with_created(user, **kwargs)
        return obj

    @staticmethod
    def by_tg_username(username) -> 'ServerMember':
        return ServerMember.objects.filter(username=username).first()

    @property
    def dm_channel(self):
        if self.pk < 0:
            return
        if not self._dm_channel:
            channel = get_api_session().post('https://discordapp.com/api/v6/users/@me/channels', json={
                'recipient_id': self.id
            }).json()
            self._dm_channel = channel['id']
            self.save()
        return self._dm_channel

    def send_message(self, content):
        if self.id > 0:
            send_discord_message(self.dm_channel, content)
        else:
            from app.bot.telegram import get_bot
            get_bot().send_message(self.pk + 10**10, content)

    @property
    def wallet_address(self):
        if not self._wallet_address:
            self._wallet_address = client.create_address(str(self.pk))
            self.save()
        return self._wallet_address

    @property
    def unconfirmed_balance(self):
        return self.received_unconfirmed - self.received

    @property
    def bitcoin_unconfirmed_balance(self):
        return self.bitcoin_received_unconfirmed - self.bitcoin_received

    @property
    def staking_wallet_address(self):
        if not self._staking_wallet_address:
            self._staking_wallet_address = staking_client.create_address(str(self.pk))
            self.save()
        return self._staking_wallet_address

    @property
    def bitcoin_wallet_address(self):
        if not self._bitcoin_wallet_address:
            self._bitcoin_wallet_address = bitcoin_client.create_address(str(self.pk))
            self.save()
        return self._bitcoin_wallet_address

    def staking_unspent(self, minconf=None):
        if minconf is None:
            minconf = 2
        return staking_client.api.listunspent(minconf, 2147483647, [self.staking_wallet_address])

    @property
    def staking_unspent_amount(self):
        return sum(b['amount'] for b in self.staking_unspent(0))

    @property
    def staking_immature_amount(self):
        transactions = staking_client.api.listtransactions(str(self.pk), 2147483647)
        transactions = filter(
            lambda t: t.get('generated') and t['confirmations'] <= global_preferences['general__staking_confirmations'],
            transactions
        )
        return sum(t['amount'] for t in transactions)

    @property
    def staking_balance(self):
        if self.is_staking_pool:
            return self.staking_pool_amount - self.pending_unstaking
        else:
            return self.staking_unspent_amount + self.staking_immature_amount

    @property
    def pending_unstaking(self):
        return self.unstakings.filter(fulfilled=False).aggregate(s=Sum('amount'))['s'] or 0

    @property
    def pending_mn_withdraw(self):
        return MasternodeWithdraw.objects.filter(fulfilled=False, member=self).aggregate(s=Sum('amount'))['s'] or 0

    @property
    def rank_display(self):
        activity = [
            0,
            60 * 24,
            60 * 24 * 3,
            60 * 24 * 5,
            60 * 24 * 8,
            60 * 24 * 14,
        ]

        xp = [
            0,
            0,
            global_preferences['ranks__junior_xp'],
            global_preferences['ranks__experienced_xp'],
            global_preferences['ranks__veteran_xp'],
            global_preferences['ranks__guru_xp'],
        ]

        msg = []
        try:
            msg.append('{} XP'.format(max(xp[self.rank+1] - self.xp, 0)))
        except IndexError:
            pass
        try:
            msg.append('{} minutes online'.format(max(activity[self.rank+1] - self.activity_counter, 0)))
        except IndexError:
            pass

        if msg:
            return '{} ({} to next rank)'.format(self.get_rank_display(), ', '.join(msg))
        return self.get_rank_display()

    @staticmethod
    def total_balance():
        return ServerMember.objects.aggregate(total_balance=Sum('balance'))['total_balance'] or 0

    def update_investor_role(self):
        if self.pk < 0:
            return
        task = UpdateRoleTask(member=self)
        if self.masternode_balance + self.staking_balance >= Decimal('100.'):
            task.add_roles = global_preferences['ranks__investor_role_id']
        else:
            task.remove_roles = global_preferences['ranks__investor_role_id']
        task.save()

        # m = get_member(global_preferences['general__guild_id'], self.pk)
        # sleep(1)
        # if not m:
        #     return
        # m_roles = set(m.get('roles', []))
        # if self.masternode_balance >= Decimal('.1') or self.staking_balance >= Decimal('.1'):
        #     if global_preferences['ranks__investor_role_id'] in m_roles:
        #         return
        #     m_roles.add(global_preferences['ranks__investor_role_id'])
        # else:
        #     if global_preferences['ranks__investor_role_id'] not in m_roles:
        #         return
        #     m_roles -= set(global_preferences['ranks__investor_role_id'])
        # r = set_roles(global_preferences['general__guild_id'], self.pk, list(m_roles))
        # sleep(1)
        # if r.status_code != 204:
        #     logging.error('Roles update error')
        #     logging.error(m)
        #     logging.error(m_roles)
        #     logging.error(r.text)


class ServerInvite(models.Model):
    code = models.CharField(max_length=64)
    uses = models.PositiveIntegerField(default=0)

    def __str__(self):
        return '{} ({} uses)'.format(self.code, self.uses)


class Broadcast(models.Model):
    content = models.TextField()
    finished = models.BooleanField(default=False)
    user_list = models.TextField()
    progress = models.PositiveIntegerField(default=0)

    def display_progress(self):
        return '{}/{}'.format(self.progress, len(self.user_list.split(',')))


class Unstaking(models.Model):
    member = models.ForeignKey(ServerMember, on_delete=models.CASCADE, related_name='unstakings')
    amount = models.DecimalField(max_digits=32, decimal_places=8)
    fulfilled = models.BooleanField(default=False)
    fulfill_at = models.DateTimeField(null=True)


class MasternodeWithdraw(models.Model):
    member = models.ForeignKey(ServerMember, on_delete=models.CASCADE, related_name='mn_withdraws')
    amount = models.DecimalField(max_digits=32, decimal_places=8)
    fulfill_at = models.DateTimeField()
    fulfilled = models.BooleanField(default=False)


class Masternode(models.Model):
    alias = models.CharField(max_length=64)
    address = models.CharField(max_length=64, help_text='IP:port')
    privkey = models.CharField(max_length=128)
    output_txid = models.CharField(max_length=128, null=True, blank=True)
    output_idx = models.PositiveIntegerField(null=True, blank=True)
    active = models.BooleanField(default=False)
    weight = models.PositiveIntegerField(default=0, blank=False, null=False)

    @property
    def config_line(self):
        line = '{} {} {} {} {}'.format(self.alias, self.address, self.privkey, self.output_txid, self.output_idx)
        if not self.active:
            line = '# ' + line
        return line

    @classmethod
    def generate_config(cls):
        result = [
            '# Masternode config file',
            '# Format: alias IP:port masternodeprivkey collateral_output_txid collateral_output_index',
            '# Example: mn1 127.0.0.2:45369 93HaYBVUCYjEMeeH1Y4sBGLALQZE1Yc1K64xiqgX37tGBDQL8Xg '
            '2bcd3c84c84f87eaa86e4e56834c92927a07f9e18718810b92e0d0324456a67c 0',
        ]
        for m in cls.objects.all():
            result.append(m.config_line)
        return '\n'.join(result)

    def __str__(self):
        return '{} ({})'.format(self.alias, self.address)

    class Meta:
        ordering = 'weight',


class TradeOrder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4)
    member = models.ForeignKey(ServerMember, on_delete=models.SET_NULL, null=True)
    is_sell = models.BooleanField()
    amount = models.DecimalField(max_digits=32, decimal_places=8)
    btc_price = models.DecimalField(max_digits=32, decimal_places=8)

    @transaction.atomic
    def try_execution(self):
        if self.is_sell:
            competing = TradeOrder.objects.filter(amount__gt=0, is_sell=False, btc_price__gte=self.btc_price) \
                .order_by('-btc_price').select_for_update()
        else:
            competing = TradeOrder.objects.filter(amount__gt=0, is_sell=True, btc_price__lte=self.btc_price) \
                .order_by('btc_price').select_for_update()
        for o in competing:
            am = min(o.amount, self.amount)
            pr = max(o.btc_price, self.btc_price) if self.is_sell else min(o.btc_price, self.btc_price)
            o.amount -= am
            o.save()
            self.amount -= am
            self.save()
            buyer, seller = (o.member, self.member) if self.is_sell else (self.member, o.member)
            buyer = ServerMember.objects.select_for_update().get(pk=buyer.pk)
            seller = ServerMember.objects.select_for_update().get(pk=seller.pk)
            if buyer.pk == seller.pk:
                buyer = seller

            buyer.balance += am
            buyer.bitcoin_balance += (max(self.btc_price, o.btc_price) - pr) * am
            buyer.save()
            tx_logger.warning('BUY,{},+{:.8f}'.format(buyer, am))
            buyer.send_message('Bought {:.8f} for {:.8f} BTC'.format(am, am * pr))

            seller.bitcoin_balance += am * pr
            seller.save()
            seller.send_message('Sold {:.8f} for {:.8f} BTC'.format(am, am * pr))

            OrderLog.objects.create(amount=am, btc_price=pr, is_sell=self.is_sell)

            if not self.amount:
                return


class OrderLog(models.Model):
    datetime = models.DateTimeField(auto_now_add=True)
    amount = models.DecimalField(max_digits=32, decimal_places=8)
    btc_price = models.DecimalField(max_digits=32, decimal_places=8)
    is_sell = models.BooleanField(default=True)


class LotteryTicket(models.Model):
    member = models.ForeignKey(ServerMember, on_delete=models.CASCADE)
    value = models.PositiveSmallIntegerField()


class UserNode(models.Model):
    member = models.ForeignKey(ServerMember, on_delete=models.CASCADE, related_name='usernodes')
    address = models.TextField()
    privkey = models.TextField()
    wallet_address = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    output_txid = models.CharField(max_length=128, null=True, blank=True)
    output_idx = models.PositiveIntegerField(null=True, blank=True)
    pending = models.BooleanField(default=True)
    active = models.BooleanField(default=True)

    @property
    def alias(self):
        return 'u{}'.format(self.member_id)

    @property
    def config_line(self):
        return '{} {} {} {} {}'.format(self.alias, self.address, self.privkey, self.output_txid, self.output_idx)

    @classmethod
    def generate_config(cls):
        result = [
            '# Masternode config file',
            '# Format: alias IP:port masternodeprivkey collateral_output_txid collateral_output_index',
            '# Example: mn1 127.0.0.2:45369 93HaYBVUCYjEMeeH1Y4sBGLALQZE1Yc1K64xiqgX37tGBDQL8Xg '
            '2bcd3c84c84f87eaa86e4e56834c92927a07f9e18718810b92e0d0324456a67c 0',
        ]
        for m in cls.objects.filter(active=True):
            result.append(m.config_line)
        return '\n'.join(result)


class UpdateRoleTask(models.Model):
    member = models.ForeignKey(ServerMember, on_delete=models.CASCADE)
    remove_roles = models.TextField(null=True)
    add_roles = models.TextField(null=True)
    processed = models.BooleanField(default=False, db_index=True)


class AirdropTask(models.Model):
    member = models.ForeignKey(ServerMember, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=32, decimal_places=8)
    processed = models.BooleanField(default=False, db_index=True)
    is_rain = models.BooleanField(default=False)


class MasternodeBalanceLog(models.Model):
    member = models.ForeignKey(ServerMember, on_delete=models.CASCADE)
    delta = models.DecimalField(max_digits=32, decimal_places=8)
    balance = models.DecimalField(max_digits=32, decimal_places=8)
    datetime = models.DateTimeField(default=now)


class MNInvestTask(models.Model):
    member = models.ForeignKey(ServerMember, on_delete=models.CASCADE)
    amount_without_fee = models.DecimalField(max_digits=32, decimal_places=8)
    amount = models.DecimalField(max_digits=32, decimal_places=8)
    processed = models.BooleanField(default=False, db_index=True)


class TGRainTask(models.Model):
    member = models.ForeignKey(ServerMember, on_delete=models.CASCADE)
    message_id = models.BigIntegerField(null=True)
    users = models.TextField(default='')
    users_cnt = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=32, decimal_places=8)
    execute_at = models.DateTimeField()
    finished = models.BooleanField(default=False)
    _chat_id = models.BigIntegerField(null=True, blank=True)

    @property
    def chat_id(self):
        return self._chat_id or global_preferences['general__telegram_chat_id']

    def render_info(self):
        return 'Rain of {} SOVE by {} will be made at {} UTC.\n' \
               'Press the button below to participate.\n\n' \
               '*{}* users participating'.format(fd(self.amount),
                                                 mention_markdown(self.member.pk + 10**10, self.member.name),
                                                 self.execute_at.strftime('%H:%M, %d %b %Y'),
                                                 len(self.users.split('|')) - 1)


class TrackedMasternode(models.Model):
    member = models.ForeignKey(ServerMember, on_delete=models.CASCADE, related_name='tracked_masternodes')
    addr = models.CharField(max_length=64)
    last_check_status = models.CharField(max_length=32)

    def __str__(self):
        return self.addr



