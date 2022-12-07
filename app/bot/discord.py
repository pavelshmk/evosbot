import asyncio
import io
import itertools
import json
import logging
import math
import os
import re
import socket
import sys
import tempfile
import threading
import traceback
import hashlib
from datetime import timedelta, datetime
from decimal import Decimal, getcontext
from random import randint, sample
from secrets import randbelow
from typing import Union

import discord
import pyotp
import qrcode
from discord import Message, Member, TextChannel, Guild, User, Status, File, Activity, ActivityType, DMChannel, Role
from discord.ext import commands, tasks
from discord.ext.commands import Context, DefaultHelpCommand, CommandError, Command, Group
from django.core.exceptions import ValidationError
from django.db import transaction
from django.template.loader import render_to_string
from django.utils.timezone import now
from django.db.models import Sum, F
from dynamic_preferences.registries import global_preferences_registry
from weasyprint import HTML

from app.bot import get_status, process_staking, SendMessage, process_unstaking, process_stakingmode, process_mninvest, \
    process_mnwithdraw, process_sendbtc, process_send, process_otp_confirm, process_otp_setup, process_otp_threshold, \
    process_otp_disable, trackmn, untrackmn, trackmnlist
from app.models import ServerMember, Broadcast, ServerInvite, Unstaking, MasternodeWithdraw, TradeOrder, LotteryTicket, \
    UserNode, Masternode, OrderLog, MasternodeBalanceLog, MNInvestTask, TrackedMasternode, AirdropTask
from evosbot.utils import client, staking_client, staking_pool_client, staking_pool_address, masternode_client, \
    masternode_address, get_masternode_price, usernode_client, bitcoin_client, get_rewards, send_stats, tx_logger, fd, \
    send_discord_message

global_preferences = global_preferences_registry.manager()


class CustomHelpCommand(DefaultHelpCommand):
    async def filter_commands(self, commands, *, sort=False, key=None):
        res = await super().filter_commands(commands)  # type: list
        res.sort(key=lambda cmd: cmd.order_index)
        return res

    def _add_to_bot(self, bot):
        super()._add_to_bot(bot)
        self._command_impl.order_index = 99999999999
    
    
class CustomCommand(Command):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_index = kwargs.get('order_index', -1)


class CustomGroup(Group):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_index = kwargs.get('order_index', -1)
        
        
def command(name=None, cls=None, **attrs):
    if not cls:
        cls = CustomCommand
    def decorator(func):
        if isinstance(func, cls):
            raise TypeError('Callback is already a command.')
        return cls(func, name=name, **attrs)
    return decorator


def group(name=None, **attrs):
    return command(name, CustomGroup, **attrs)


def prefix(b, msg: Message):
    if isinstance(msg.channel, DMChannel):
        return ['$', '']
    return '$'


def get_bot(loop=None, self_bot=False):
    intents = discord.flags.Intents.all()
    return commands.Bot(
        command_prefix=prefix,
        help_command=CustomHelpCommand(verify_checks=False, dm_help=True, sort_commands=False),
        self_bot=self_bot,
        loop=loop,
        case_insensitive=True,
        intents=intents
    )


bot = get_bot()


class BackgroundTasks(commands.Cog):
    def __init__(self, bot):
        self.activity_index = 0
        self.update_online.start()
        self.stats.start()
        self.activity.start()

    def cog_unload(self):
        self.update_online.cancel()
        self.stats.cancel()
        self.activity.cancel()

    @tasks.loop(seconds=5)
    async def update_online(self):
        try:
            guild = bot.get_guild(global_preferences['general__guild_id'])
            online_users = [m.id for m in guild.members if m.status != Status.offline and not m.bot]
            with open('/tmp/evos_online.json', 'w') as f:
                json.dump(online_users, f)
            online_users_dict = {m.id: [str(r.id) for r in m.roles]
                                 for m in guild.members if m.status != Status.offline and not m.bot}
            with open('/tmp/evos_online_with_roles.json', 'w') as f:
                json.dump(online_users_dict, f)
        except:
            pass

    @tasks.loop(seconds=global_preferences['general__stats_interval'])
    async def stats(self):
        threading.Thread(target=send_stats).start()

    @tasks.loop(seconds=5)
    async def activity(self):
        try:
            activity_index = self.activity_index
            if activity_index == 0:
                activity_text = 'CREX24 price: ${:.2f}'.format(global_preferences['internal__crex24_price'])
            elif activity_index == 1:
                activity_text = 'CREX24 24h vol: {} BTC'.format(fd(global_preferences['internal__crex24_volume']))
            elif activity_index == 2:
                activity_text = 'Graviex price: ${:.2f}'.format(global_preferences['internal__graviex_price'])
            elif activity_index == 3:
                activity_text = 'Graviex 24h vol: {} BTC'.format(fd(global_preferences['internal__graviex_volume']))
            #            elif activity_index == 4:
            #                activity_text = 'CB price: ${:.2f}'.format(global_preferences['internal__cryptobridge_price'])
            #            elif activity_index == 5:
            #                activity_text = 'CB 24h vol: {} BTC'.format(fd(global_preferences['internal__cryptobridge_volume']))
            elif activity_index == 4:
                guild = bot.get_guild(global_preferences['general__guild_id'])
                online_count = len([m.id for m in guild.members if m.status != Status.offline and not m.bot])
                activity_text = 'Online: {} users'.format(online_count)
            elif activity_index == 5:
                activity_text = 'Block height: {}'.format(client.api.getblockcount())
            else:
                activity_text = '---'
            self.activity_index = (activity_index + 1) % 6
            if activity_text:
                activity = Activity(type=ActivityType.playing, name=activity_text)
                await bot.change_presence(activity=activity)
        except:
            pass


@bot.event
async def on_ready():
    print('Logged on as', bot.user)


@bot.event
async def on_command_error(ctx: Context, error):
    if hasattr(ctx.command, 'on_error'):
        return

    ignored = commands.CommandNotFound,

    if isinstance(error, ignored):
        return
    elif isinstance(error, commands.DisabledCommand):
        return await ctx.send('{} has been disabled'.format(ctx.command))
    elif isinstance(error, commands.NoPrivateMessage):
        return await ctx.send('{} can not be used in Private Messages'.format(ctx.command))
    elif isinstance(error, (commands.BadArgument, commands.MissingRequiredArgument, commands.BadUnionArgument)):
        logging.warning(ctx.command.name)
        if ctx.command.name == 'like':
            return await ctx.send('Usage: `$like @mention`')
        elif ctx.command.name == 'dislike':
            return await ctx.send('Usage: `$dislike @mention`')
        elif ctx.command.name == 'send':
            return await ctx.send('Usage: `$send <@mention or wallet address> amount [2fa code]`')
        elif ctx.command.name == 'rain':
            return await ctx.send('Usage: `$rain amount users_count [@role]` (users count should be between 1 and 50)')
        elif ctx.command.name == 'lottery':
            return await ctx.send('Usage: `$lottery value` (value should be between 0 and 255)')
        elif ctx.command.name == 'dice':
            return await ctx.send('Usage: `$dice amount`')
        elif ctx.command.name == 'feeder_deposit':
            return await ctx.send('Usage: `$feeder_deposit amount`')
        elif ctx.command.name == 'staking':
            return await ctx.send('Usage: `$staking amount`')
        elif ctx.command.name == 'unstaking':
            return await ctx.send('Usage: `$unstaking amount`')
        elif ctx.command.name == 'stakingmode':
            return await ctx.send('Usage: `$stakingmode mode` (mode should be either `pool` or `individual`)')
        elif ctx.command.name == 'mninvest':
            return await ctx.send('Usage: `$mninvest amount` (amount is either decimal or "all")')
        elif ctx.command.name == 'mnwithdraw':
            return await ctx.send('Usage: `$mnwithdraw amount`')
        elif ctx.command.name == 'buy':
            return await ctx.send('Usage: `$buy <sove_amount> <price_in_satoshis>`')
        elif ctx.command.name == 'sell':
            return await ctx.send('Usage: `$sell <sove_amount> <price_in_satoshis>`')
        elif ctx.command.name == 'cancelorder':
            return await ctx.send('Usage: `$cancelorder order_id`')
        elif ctx.command.name == 'startnode':
            return await ctx.send('Usage: `$startnode VPS_IP:PORT private_key_from_VPS`\n'
                                  'Example: `$startnode 127.0.0.2:18976 88Pb77CdDNm2WmqDn8YpYV2y6RQX7hsX11U7fxWk1U28EoHMZb3`')
        elif ctx.command.name == 'stopnode':
            return await ctx.send('Usage: `$stopnode node_id`')
        elif ctx.command.name == 'sendbtc':
            return await ctx.send('Usage: `$sendbtc address amount`')
        elif ctx.command.name == 'broadcast':
            return await ctx.send('Usage: `$broadcast broadcast_id`')
        elif ctx.command.name == 'trackmn':
            return await ctx.send('Usage: `$trackmn <wallet address>`')
        elif ctx.command.name == 'untrackmn':
            return await ctx.send('Usage: `$untrackmn <wallet address>`')
        elif ctx.command.full_parent_name == '2fa':
            return await ctx.send('Send `$2fa` to get info about currently available commands')

        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


@bot.event
async def on_member_join(member: Member):
    guild = bot.get_guild(global_preferences['general__guild_id'])
    invites = await guild.invites()
    invites_dict = {i.code: i for i in invites}
    server_invites = ServerInvite.objects.filter(code__in=list(invites_dict.keys()))
    referrer = None
    for si in server_invites:
        if si.code not in invites_dict:
            continue
        invite = invites_dict[si.code]
        if si.uses != invite.uses:
            si.uses += 1
            si.save()
            try:
                referrer = ServerMember.objects.get(pk=invite.inviter.id)
                break
            except ServerMember.DoesNotExist:
                continue
    sm, created = ServerMember.from_member_with_created(member, referrer=referrer)
    if created:
        await member.send('Hey. I’m Soverain Bot and still work in a test mode, but you can use all the features that are available.\n' 
                          'Your wallet has already been created, enter the “status” and you will see it, and the “help” command will help you with everything else!\n'
                          'If you have any difficulties or questions, please contact my developers!\n')
        # if referrer and member.created_at <= datetime.now() - global_preferences['general__min_account_age']:
        #     from app.tasks import check_referral
        #     check_referral.s(sm.id).apply_async(countdown=randint(0, 10))  # TODO: change delay


@bot.event
async def on_message(message: Message):
    if message.content.startswith('$') or isinstance(message.channel, DMChannel):
        return await bot.process_commands(message)
    if message.author == bot.user or message.author.bot:
        return
    if not isinstance(message.channel, TextChannel) or \
            str(message.channel.id) in global_preferences['ranks__ignored_channels']:
        return
    if len(message.clean_content) < 50:
        return
    sm = ServerMember.from_member(message.author)
    if not sm.last_message or now() - sm.last_message > timedelta(seconds=60 + randint(0, 60)):
        sm.xp += 1
        sm.last_message = now()
        sm.save()


class ServerCommands(commands.Cog, name='Server commands (starts with $)'):
    @command(help='To show your sympathy', aliases=['love'], order_index=1)
    @commands.guild_only()
    async def like(self, ctx: Context, mention: Member):
        if mention.id == ctx.author.id:
            await ctx.send('You cannot like yourself!')
            return
        author = ServerMember.from_member(ctx.author)
        if author.last_like and now() - author.last_like < timedelta(hours=1):
            await ctx.send('You liked someone less than an hour ago')
            return
        if not author.rank:
            await ctx.send('Your rank is Brand New, so you cannot like, please wait until your rank is increased')
            return
        sm = ServerMember.from_member(mention)
        if not sm.rank:
            await ctx.send('You cannot like users with Brand New rank')
            return
        sm.xp += Decimal('.25')
        sm.activity_counter += 1
        sm.save()
        author.last_like = now()
        author.save()
        await ctx.send('{} increased {}\'s XP by 0.25 and activity by 1 minute, current value XP: {}, activity: {} minutes'.format(ctx.author.mention, mention.mention, sm.xp, sm.activity_counter))

    @command(help='To show your antipathy', order_index=2)
    @commands.guild_only()
    async def dislike(self, ctx: Context, mention: Member):
        if mention.id == ctx.author.id:
            await ctx.send('You cannot dislike yourself!')
            return
        author = ServerMember.from_member(ctx.author)
        if author.last_dislike and now() - author.last_dislike < timedelta(hours=1):
            await ctx.send('You disliked someone less than an hour ago')
            return
        if not author.rank:
            await ctx.send('Henceforth Brand New can\'t do dislike, please wait until your rank is increased')
            return
        sm = ServerMember.from_member(mention)
        if not sm.rank:
            await ctx.send('You cannot dislike users with Brand New rank')
            return
        if sm.xp - Decimal('.25') < 0:
            return await ctx.send('Cannot decrease XP below 0')
        sm.xp -= Decimal('.25')
        sm.save()
        author.last_dislike = now()
        author.save()
        await ctx.send('{} decreased {}\'s XP by 0.25, current value: {}'.format(ctx.author.mention, mention.mention, sm.xp))

    @command(help='Decrease XP by 1, __mods_only__', hidden=True, order_index=3)
    @commands.guild_only()
    @commands.has_any_role("core team","moderator","mod")
    async def dexp(self, ctx: Context, mention: Member):
        sm = ServerMember.from_member(mention)
        if sm.xp - Decimal('1.0') < 0:
            return await ctx.send('Cannot decrease XP below 0')
        sm.xp -= Decimal('1.0')
        sm.save()
        await ctx.send('Mod {} decreased {}\'s XP by 1, current value: {}'.format(ctx.author.mention, mention.mention, sm.xp))

    @command(help='Check user status __staff_only__', hidden=True, order_index=4)
    @commands.guild_only()
    async def check(self, ctx: Context, mention: Member):
        sm = ServerMember.from_member(mention)
        message = '\n\nUSERNAME: <@{}>\n'.format(sm.pk) + get_status(sm)
        send_discord_message(global_preferences['general__rescue_channel'], message)
        sm.update_investor_role()

    @command(help='Send coins from your wallet. Also works in a bot chat', order_index=5)
    async def send(self, ctx: Context, to: Union[Member, str], amount: Decimal, otp: str = None):
        logging.warning(to)
        sm = ServerMember.from_member(ctx.author)
        if isinstance(to, Member):
            to = ServerMember.from_member(to)
        try:
            logging.warning(to)
            process_send(sm, to, amount, otp)
        except SendMessage as e:
            await ctx.send(e.msg)
        except:
            traceback.print_exc()

    @command(help='Show top referrers', hidden=True, order_index=6)
    async def top_S1(self, ctx: Context):
        qs = ServerMember.objects.filter(confirmed_referrals__gt=0).order_by('-confirmed_referrals')[:15]
        map(lambda mid: ServerMember.from_member(ctx.guild.get_member(mid)), qs.values_list('pk', flat=True))
        html = render_to_string('top.html', {'users': qs})
        await ctx.send(file=File(io.BytesIO(HTML(string=html).write_png()), 'top.png'))

    @command(help='Rain your SOVE on online users. Amount is divided in equal parts '
                           'by the specified number of users. Works everywhere!', order_index=7)
    async def rain(self, ctx: Context, amount: Decimal, users_cnt: int, role: Role = None):
        getcontext().prec = 8

        if not (0 < users_cnt <= 50):
            return await ctx.send('Users count should be in interval 1..50')

        with transaction.atomic():
            sm = ServerMember.from_member(ctx.author)
            sm = ServerMember.objects.select_for_update().get(pk=sm.pk)
            if sm.balance < amount:
                return await ctx.send('Insufficient funds')
            guild = bot.get_guild(global_preferences['general__guild_id'])  # type: Guild
            online_members = list(filter(lambda m: m.status != Status.offline and not m.bot and m.id != sm.pk,
                                         guild.members))
            if role:
                online_members = list(filter(lambda m: m.mentioned_in(ctx.message), online_members))
            users_cnt = min(users_cnt, len(online_members)) or len(online_members)
            if not users_cnt:
                return await ctx.send('There\'s no one on this server to rain tokens on')
            selected_users = sample(online_members, k=users_cnt)
            reward = amount / users_cnt
            if reward <= 0:
                return await ctx.send('Amount is too small')
            sm.balance -= reward * users_cnt
            sm.save()
            tx_logger.warning('RAIN,{},-{:.8f}'.format(sm, amount))

            def _():
                tasks = []
                for user in selected_users:
                    with transaction.atomic():
                        member = ServerMember.from_member(user)
                        tasks.append(AirdropTask(member=member, amount=reward, is_rain=True))
                AirdropTask.objects.bulk_create(tasks)
                sm.send_message('Rain was queued')

            thread = threading.Thread(target=_)
            thread.start()

    @command(help='Play a lottery', order_index=8)
    async def lottery(self, ctx: Context, value: int):
        if ctx.channel.id != global_preferences['games__games_channel_id']:
            return await ctx.send('This command only can be used in the #games channel')

        with transaction.atomic():
            ticket_price = global_preferences['games__lottery_ticket_price']
            sm = ServerMember.from_member(ctx.author)
            sm = ServerMember.objects.select_for_update().get(pk=sm.pk)

            if value < 0 or value > 255:
                return await ctx.send('Value must be between 0 and 255')
            if sm.balance < ticket_price:
                return await ctx.send('Insufficient funds')

            sm.balance -= ticket_price
            sm.save()
            tx_logger.warning('LOTTERY,{},-{:.8f}'.format(sm, ticket_price))
            LotteryTicket.objects.create(member=sm, value=value)
            global_preferences['internal__lottery_jackpot'] += ticket_price * Decimal('.95')
            await ctx.send('Ticket was successfully bought. Jackpot: {}'.format(
                fd(global_preferences['internal__lottery_jackpot'])
            ))

    @command(help='Play dice', order_index=9)
    async def dice(self, ctx: Context, amount: Decimal):
        if ctx.channel.id != global_preferences['games__games_channel_id']:
            return await ctx.send('This command only can be used in the #games channel')

        def generate_image(dice1, dice2, result):
            html = render_to_string('dice.html', {'dice1': dice1, 'dice2': dice2, 'result': result})
            return io.BytesIO(HTML(string=html).write_png())

        with transaction.atomic():
            sm = ServerMember.from_member(ctx.author)
            sm = ServerMember.objects.select_for_update().get(pk=sm.pk)
            if amount > sm.balance:
                return await ctx.send('Insufficient funds')
            if amount < Decimal('.05'):
                return await ctx.send('Minumum bet amount is: 0.05 SOVE')

            sm.balance -= amount
            sm.save()
            tx_logger.warning('DICE,{},-{:.8f}'.format(sm, amount))
            global_preferences['internal__dice_jackpot'] += amount * Decimal('.95')
            dice1, dice2 = randbelow(6) + 1, randbelow(6) + 1
            if dice1 + dice2 != 10:
                message = 'You lost! Jackpot is: {} SOVE'.format(fd(global_preferences['internal__dice_jackpot']))
                return await ctx.send(file=File(generate_image(dice1, dice2, message), 'dice.png'))
            win_amount = min(global_preferences['internal__dice_jackpot'], amount * 10)
            if not randbelow(50):
                win_amount = global_preferences['internal__dice_jackpot']

            global_preferences['internal__dice_jackpot'] -= win_amount
            sm.balance += win_amount
            sm.save()
            tx_logger.warning('DICE,{},+{:.8f}'.format(sm, win_amount))
            message = 'You won {} SOVE!'.format(fd(win_amount))
            await ctx.send(file=File(generate_image(dice1, dice2, message), 'dice.png'))
            if not global_preferences['internal__dice_jackpot'] and \
                    global_preferences['general__feeder_balance'] >= global_preferences['games__dice_jackpot_refill']:
                global_preferences['internal__dice_jackpot'] = global_preferences['games__dice_jackpot_refill']
                global_preferences['general__feeder_balance'] -= global_preferences['games__dice_jackpot_refill']

    @command(help='Deposit to bounty/airdrops address (Help the community!)', hidden=True, order_index=10)
    async def feeder_deposit(self, ctx: Context, amount: Decimal):
        with transaction.atomic():
            sm = ServerMember.from_member(ctx.author)
            sm = ServerMember.objects.select_for_update().get(pk=sm.pk)
            if amount > sm.balance:
                return await ctx.send('Insufficient funds')
            sm.balance -= amount
            sm.save()
            global_preferences['general__feeder_balance'] += amount
            await ctx.send('Feeder deposit was performed successfully, current balance: {}'.format(
                fd(global_preferences['general__feeder_balance'])
            ))
            tx_logger.warning('FEEDER,{},-{:.8f}'.format(sm, amount))

    @command(hidden=True, order_index=11)
    async def stats_S1(self, ctx: Context):
        await ctx.send('Preparing stats...')
        t = threading.Thread(target=send_stats, args=(ctx.channel.id,))
        t.start()

    @command(hidden=True, order_index=12)
    async def chid(self, ctx: Context):
        await ctx.send('`{}`'.format(ctx.channel.id))


class PrivateCommands(commands.Cog, name='Private commands'):
    @command(help='Show your Soverain address, wallet balance, rank, etc.', order_index=13)
    @commands.dm_only()
    async def status(self, ctx: Context):
        sm = ServerMember.from_member(ctx.author)
        await ctx.send(get_status(sm))
        sm.update_investor_role()

    @command(help='Get rescue code. Pass this code to the administrator to refund your coins '
                           'if your Discord account has been disabled or deleted', order_index=14)
    @commands.dm_only()
    async def rescue(self, ctx: Context):
        sm = ServerMember.from_member(ctx.author)
        send_discord_message(global_preferences['general__rescue_channel'], 'User: <@{}> got rescue code'.format(sm.pk))
        await ctx.send(hashlib.scrypt(sm.id.to_bytes(8, byteorder='little'), salt=b'KL3982872uu2cjiOCz', n=16, r=1, p=1, dklen=16).hex())

    @command(help='Show your Earn-by-Invite bounty status', hidden=True, order_index=15)
    @commands.dm_only()
    async def invite_S1(self, ctx: Context):
        sm = ServerMember.from_member(ctx.author)
        lvl1_referrals = ServerMember.objects.filter(referrer=sm).count()
        lvl1_confirmed_referrals = ServerMember.objects.filter(referrer=sm,
                                                               rank__gt=ServerMember.Rank.BRAND_NEW).count()
        lvl2_referrals = ServerMember.objects.filter(referrer__referrer=sm).count()
        lvl2_confirmed_referrals = ServerMember.objects.filter(referrer__referrer=sm,
                                                               rank__gt=ServerMember.Rank.BRAND_NEW).count()
        lvl3_referrals = ServerMember.objects.filter(referrer__referrer__referrer=sm).count()
        lvl3_confirmed_referrals = ServerMember.objects.filter(referrer__referrer__referrer=sm,
                                                               rank__gt=ServerMember.Rank.BRAND_NEW).count()
        message = 'Level 1 referrals: {} (confirmed: {})\n' \
                  'Level 2 referrals: {} (confirmed: {})\n' \
                  'Level 3 referrals: {} (confirmed: {})'.format(lvl1_referrals, lvl1_confirmed_referrals,
                                                                 lvl2_referrals, lvl2_confirmed_referrals,
                                                                 lvl3_referrals, lvl3_confirmed_referrals)
        await ctx.send(message)

    @command(help='Begin staking of selected amount inside POOL.', order_index=16)
    @commands.dm_only()
    async def staking(self, ctx: Context, amount: Decimal):
        return await ctx.send('Staking pool is disabled, please use mninvest instead')
        sm = ServerMember.from_member(ctx.author)
        try:
            process_staking(sm, amount)
        except SendMessage as e:
            await ctx.send(e.msg)
        sm.update_investor_role()

    @command(help='Stop staking of selected amount. Withdrawal up to 6 hours.', order_index=17)
    @commands.dm_only()
    async def unstaking(self, ctx: Context, amount: Decimal):
        sm = ServerMember.from_member(ctx.author)
        try:
            process_unstaking(sm, amount)
        except SendMessage as e:
            await ctx.send(e.msg)
        sm.update_investor_role()

    @command(help='Toggle staking mode, POOL or INDIVIDUAL', order_index=18)
    @commands.dm_only()
    async def stakingmode(self, ctx: Context, mode: str):
        sm = ServerMember.from_member(ctx.author)
        try:
            process_stakingmode(sm, mode)
        except SendMessage as e:
            await ctx.send(e.msg)
        sm.update_investor_role()

    @command(help='Invest to **INSTANT SHARED** masternode with automatic reinvest - '
                           'start earn immediately without ANY FEES! Minimum amount: 10 SOVE', order_index=19)
    @commands.dm_only()
    async def mninvest(self, ctx: Context, amount: Union[Decimal, str]):
        sm = ServerMember.from_member(ctx.author)
        if isinstance(amount, str):
            if amount == 'all':
                amount = sm.balance
            else:
                return await ctx.send('Usage: `$mninvest amount` (amount is either decimal or "all")')
        try:
            process_mninvest(sm, amount)
        except SendMessage as e:
            await ctx.send(e.msg)

    @command(help='Withdraw from masternode. Processing time no more than 24 hours!', order_index=20)
    @commands.dm_only()
    async def mnwithdraw(self, ctx: Context, amount: Decimal):
        # return await ctx.send('Withdrawals are currently disabled, please try again later')
        sm = ServerMember.from_member(ctx.author)
        try:
            process_mnwithdraw(sm, amount)
        except SendMessage as e:
            await ctx.send(e.msg)

    @command(help='Place an order to buy SOVE.  buy <amount> <price_in_satoshis> '
                           'ex. $buy 10 20000', order_index=21)
    @commands.dm_only()
    async def buy(self, ctx: Context, amount: Decimal, price: int):
        with transaction.atomic():
            sm = ServerMember.from_member(ctx.author)
            sm = ServerMember.objects.select_for_update().get(pk=sm.pk)
            price = Decimal(price) / 10**8
            if sm.bitcoin_balance < amount * price:
                return await ctx.send('Insufficient funds')
            if amount <= 0 or price <= 0:
                return await ctx.send('Amount and price should be positive')
            sm.bitcoin_balance -= amount * price
            sm.save()
            to = TradeOrder.objects.create(
                member=sm,
                is_sell=False,
                amount=amount,
                btc_price=price
            )
            await ctx.send('Order #{} was created'.format(to.pk))
            to.try_execution()

    @command(help='Place an order to sell SOVE. sell <amount> <price_in_satoshis> '
                           'ex. $sell 5 30000', order_index=22)
    @commands.dm_only()
    async def sell(self, ctx: Context, amount: Decimal, price: int):
        with transaction.atomic():
            sm = ServerMember.from_member(ctx.author)
            sm = ServerMember.objects.select_for_update().get(pk=sm.pk)
            price = Decimal(price) / 10**8
            if sm.balance < amount:
                return await ctx.send('Insufficient funds')
            if amount <= 0 or price <= 0:
                return await ctx.send('Amount and price should be positive')
            sm.balance -= amount
            sm.save()
            tx_logger.warning('SELL,{},-{:.8f}'.format(sm, amount))
            to = TradeOrder.objects.create(
                member=sm,
                is_sell=True,
                amount=amount,
                btc_price=price
            )
            await ctx.send('Order #{} was created'.format(to.pk))
            to.try_execution()

    @command(help='Get up to 10 top orders and list your own', order_index=23)
    @commands.dm_only()
    async def orders(self, ctx: Context):
        sm = ServerMember.from_member(ctx.author)

        sell_qs = TradeOrder.objects.filter(is_sell=True, amount__gt=0).values('btc_price')\
            .annotate(amount=Sum('amount')).order_by('btc_price')
        sell_total = sell_qs.aggregate(sum=Sum(F('amount') * F('btc_price')))['sum'] or 0
        msg = ['```yaml', 'Sell orders (total {:.8f} BTC)'.format(sell_total)]
        for o in sell_qs[:10]:
            msg.append('- {:.8f} SOVE per {:.8f} BTC ({:.8f} BTC total)'.format(o['amount'], o['btc_price'], o['amount'] * o['btc_price']))
        msg += ['', '```']
        await ctx.send('\n'.join(msg))

        buy_qs = TradeOrder.objects.filter(is_sell=False, amount__gt=0).values('btc_price')\
            .annotate(amount=Sum('amount')).order_by('-btc_price')
        buy_total = buy_qs.aggregate(sum=Sum(F('amount') * F('btc_price')))['sum'] or 0
        msg = ['```diff', 'Buy orders (total {:.8f} BTC)'.format(buy_total)]
        for o in buy_qs[:10]:
            msg.append('- {:.8f} SOVE per {:.8f} BTC ({:.8f} BTC total)'.format(o['amount'], o['btc_price'], o['amount'] * o['btc_price']))

        msg += ['', '```']
        await ctx.send('\n'.join(msg))

        msg = ['```', 'Last orders']
        for o in OrderLog.objects.order_by('-pk')[:10]:
            msg.append('- {} {} amount: {:.8f} SOVE, price: {:.8f} BTC, total: {:.8f} BTC'.format(
                o.datetime.strftime('%Y-%m-%d %H:%M:%S'),
                'sell' if o.is_sell else 'buy',
                o.amount, o.btc_price,
                o.amount * o.btc_price)
            )
        msg += ['', '```']
        await ctx.send('\n'.join(msg))

        msg = ['```fix', 'Your orders']
        for i, o in enumerate(TradeOrder.objects.filter(member=sm, amount__gt=0), 1):
            msg.append('- #{}: {} {:.8f} SOVE per {:.8f} BTC ({:.8f} BTC total)'.format(
                o.pk, 'sell' if o.is_sell else 'buy',
                o.amount, o.btc_price,
                o.amount * o.btc_price)
            )
            if not i % 10:
                msg += ['', '```']
                await ctx.send('\n'.join(msg))
                msg = ['```fix']

        if len(msg) > 1:
            msg += ['', '```']
            await ctx.send('\n'.join(msg))

    @command(help='Cancel your order ex. cancelorder 009797b5-571b-4a9b-9608-747a68b9101d', order_index=24)
    @commands.dm_only()
    async def cancelorder(self, ctx: Context, oid: str):
        sm = ServerMember.from_member(ctx.author)

        try:
            o = TradeOrder.objects.get(member=sm, pk=oid, amount__gt=0)
        except (TradeOrder.DoesNotExist, ValidationError):
            return await ctx.send('The order was not found')
        with transaction.atomic():
            member = ServerMember.objects.select_for_update().get(pk=o.member_id)
            if o.is_sell:
                member.balance += o.amount
                tx_logger.warning('CANCELORDER,{},+{:.8f}'.format(member, o.amount))
            else:
                member.bitcoin_balance += o.amount * o.btc_price
            member.save()
        o.delete()
        await ctx.send('The order was canceled')

    @command(help='Start a personal masternode (Cold Wallet). You must have min. 3000 SOVE '
                           'on your account and provide correct IP, PORT and Private key from your VPS. '
                           'Rewards will be transferred to your main wallet automatically. To list your nodes type '
                           '$mynodes. And $stopnode <num> to return 3000 SOVE to the main wallet', order_index=25)
    @commands.dm_only()
    async def startnode(self, ctx: Context, address: str, privkey: str):
        f = lambda n: re.split(r"(?<=\]):" if n.startswith('[') else r":(?=\d)", n)
        parsed = f(address)
        if len(parsed) != 2:
            return await ctx.send('Port is not specified')
        if parsed[0].startswith('['):
            s = socket.socket(socket.AF_INET6)
            parsed = parsed[0].replace('[', '').replace(']', ''), int(parsed[1])
        else:
            s = socket.socket()
            parsed = parsed[0], int(parsed[1])
        s.settimeout(5)
        try:
            s.connect(parsed)
        except Exception:
            return await ctx.send('Address is not reachable')

        with transaction.atomic():
            sm = ServerMember.from_member(ctx.author)
            sm = ServerMember.objects.select_for_update().get(pk=sm.pk)
            masternode_price = get_masternode_price()
            total_price = masternode_price + global_preferences['general__transaction_commission']
            if sm.balance < total_price:
                return await ctx.send('Insufficient funds (required {})'.format(fd(total_price)))
            sm.balance -= total_price
            sm.save()
        tx_logger.warning('USERNODE,{},-{:.8f}'.format(sm, total_price))
        UserNode.objects.create(member=sm, address=address, privkey=privkey)
        await ctx.send('Request to start a node was created')

    @command(help='List your personal masternodes', order_index=26)
    @commands.dm_only()
    async def mynodes(self, ctx: Context):
        sm = ServerMember.from_member(ctx.author)
        nodes = ['Your nodes:']
        for un in UserNode.objects.filter(member=sm, active=True):
            line = '#{} {}\n[{}]'.format(un.pk, un.address, un.wallet_address)
            if un.pending:
                line += ' (pending)'
            nodes.append(line)
        await ctx.send('\n'.join(nodes))

    @command(help='Stop a personal masternode', order_index=27)
    @commands.dm_only()
    async def stopnode(self, ctx: Context, nid: int):
        if global_preferences['internal__usernode_lock']:
            await ctx.send('Nodes are starting. Please, try later.')
        sm = ServerMember.from_member(ctx.author)
        try:
            un = UserNode.objects.get(member=sm, pk=nid)
        except UserNode.DoesNotExist:
            return await ctx.send('Node #{} was not found'.format(nid))
        if un.pending:
            return await ctx.send('The node is starting and cannot be stopped right now')
        if not un.active:
            return await ctx.send('The node was already stopped')
        if not un.pending:
            fee = usernode_client.estimate_fee(1)
            un_price = get_masternode_price()
            inputs = [{'txid': un.output_txid, 'vout': un.output_idx, 'confirmations': 99999999999999,
                       'amount': un_price}]
            outputs = {sm.wallet_address: un_price}
            try:
                estimate_tx = usernode_client.api.createrawtransaction(inputs, outputs)
                estimate_tx = usernode_client.api.signrawtransaction(estimate_tx)
                fee *= math.ceil(len(bytes.fromhex(estimate_tx['hex'])) / 1024 + 1)

                outputs[sm.wallet_address] -= fee
                logging.warning(inputs)
                logging.warning(outputs)
                tx = usernode_client.api.createrawtransaction(inputs, outputs)
                tx = usernode_client.api.signrawtransaction(tx)
                txid = usernode_client.api.sendrawtransaction(tx['hex'])
            except:
                traceback.print_exc()
                return await ctx.send('Operation is currently unavailable, please try later')
        un.active = False
        un.save()
        await ctx.send('A node was successfully stopped')

    @command(help='Withdraw BTC from bot', order_index=28)
    @commands.dm_only()
    async def sendbtc(self, ctx: Context, address: str, amount: Decimal):
        sm = ServerMember.from_member(ctx.author)
        try:
            process_sendbtc(sm, address, amount)
        except SendMessage as e:
            await ctx.send(e.msg)

    @commands.dm_only()
    @group('2fa', order_index=29)
    async def otp(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            sm = ServerMember.from_member(ctx.author)
            if sm.otp_active:
                await ctx.send('Current 2FA status: Active\n'
                               'Threshold value: {} SOVE\n\n'
                               'Available commands:\n'
                               '`$2fa threshold <NEW_VALUE> <2fa code>` - Change threshold value\n'
                               '`$2fa disable <2fa code>` - Disable 2FA'.format(fd(sm.otp_threshold)))
            else:
                await ctx.send('Current 2FA status: Inactive\n\n'
                               'Available commands:\n'
                               '`$2fa setup` - Activate 2FA\n'
                               '`$2fa confirm <2fa code>` - After you receive a QR code, confirm activation'
                               ''.format(fd(sm.otp_threshold)))

    @otp.command(order_index=30)
    async def setup(self, ctx: Context):
        sm = ServerMember.from_member(ctx.author)
        if sm.otp_active:
            return await ctx.send('2FA is already active')
        sm.otp_secret = pyotp.random_base32()
        qr = qrcode.make(pyotp.TOTP(sm.otp_secret).provisioning_uri(sm.name, 'SOVE Bot'))
        with tempfile.TemporaryDirectory() as d:
            fpath = os.path.join(d, 'qr.png')
            qr.save(fpath)
            m = await ctx.send('Please scan this code and use command `2fa confirm <2fa code>` '
                               'to confirm activation of 2FA\n'
                               'You also can use text secret: `{}`'.format(sm.otp_secret),
                               file=File(fpath))
            sm.otp_qr_message_id = m.id
            sm.save()

    @otp.command(order_index=31)
    async def confirm(self, ctx: Context, otp: str):
        sm = ServerMember.from_member(ctx.author)
        if sm.otp_active:
            return await ctx.send('2FA is already active')
        if not sm.otp_secret:
            return await ctx.send('Use `2fa setup` command first')
        if not pyotp.TOTP(sm.otp_secret).verify(otp):
            return await ctx.send('Provided one-time password is invalid')
        m = await ctx.fetch_message(sm.otp_qr_message_id)
        await m.delete()
        sm.otp_active = True
        sm.save()
        await ctx.send('2FA was successfully activated.\nCurrent threshold: {} SOVE\n'
                       'Use `2fa threshold <NEW_VALUE> <2fa code>` command to change it.\n\n'
                       'QR code was removed for security purposes.'.format(fd(sm.otp_threshold)))

    @otp.command(order_index=32)
    async def threshold(self, ctx: Context, value: Decimal, otp: str):
        sm = ServerMember.from_member(ctx.author)

        try:
            process_otp_threshold(sm, value, otp)
        except SendMessage as e:
            await ctx.send(e.msg)

    @otp.command(order_index=33)
    async def disable(self, ctx: Context, otp: str):
        sm = ServerMember.from_member(ctx.author)

        try:
            process_otp_disable(sm, otp)
        except SendMessage as e:
            await ctx.send(e.msg)

    @command(help='Disable notifications from bot', order_index=34)
    @commands.dm_only()
    async def noinform(self, ctx: Context):
        sm = ServerMember.from_member(ctx.author)
        sm.noinform = not sm.noinform
        sm.save()
        await ctx.send('Noinform mode was {}'.format('enabled' if sm.noinform else 'disabled'))

    @command(help='Track a masternode', order_index=35)
    @commands.dm_only()
    async def trackmn(self, ctx: Context, addr: str):
        sm = ServerMember.from_member(ctx.author)

        try:
            trackmn(sm, addr)
        except SendMessage as e:
            await ctx.send(e.msg)
    
    @command(help='Stop masternode tracking', order_index=36)
    @commands.dm_only()
    async def untrackmn(self, ctx: Context, addr: str):
        sm = ServerMember.from_member(ctx.author)

        try:
            untrackmn(sm, addr)
        except SendMessage as e:
            await ctx.send(e.msg)

    @command(help='List tracked masternodes', order_index=37)
    @commands.dm_only()
    async def trackmnlist(self, ctx: Context):
        sm = ServerMember.from_member(ctx.author)

        try:
            trackmnlist(sm)
        except SendMessage as e:
            await ctx.send(e.msg)

    @command(hidden=True, order_index=38)
    @commands.dm_only()
    async def broadcast(self, ctx: Context, bid: int):
        try:
            broadcast = Broadcast.objects.get(pk=bid)
        except Broadcast.DoesNotExist:
            await ctx.send('Broadcast with ID={} was not found'.format(bid))
            return
        if broadcast.finished:
            await ctx.send('Broadcast with ID={} is already finished'.format(bid))
            return
        if not broadcast.progress:
            guild = bot.get_guild(global_preferences['general__guild_id'])  # type: Guild
            sorted_members = sorted(guild.members, key=lambda m: 0 if m.status != Status.offline else 1)
            broadcast.user_list = ','.join([str(m.id) for m in sorted_members])
            broadcast.save()
        for uid in broadcast.user_list.split(',')[broadcast.progress:]:
            try:
                user = await bot.fetch_user(int(uid))  # type: User
                if user.bot:
                    continue
                await user.send(broadcast.content)
            except:
                pass
            broadcast.progress += 1
            broadcast.save()
        broadcast.finished = True
        broadcast.save()
        await ctx.send('Broadcast ID={} was successfully finished'.format(bid))


bot.add_cog(BackgroundTasks(bot))
bot.add_cog(ServerCommands(bot))
bot.add_cog(PrivateCommands(bot))
