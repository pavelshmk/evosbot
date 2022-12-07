import os
import re
import tempfile
from datetime import timedelta
from decimal import Decimal
from random import randint

import pyotp
import qrcode
from django.db import transaction
from django.utils.timezone import now
from dynamic_preferences.registries import global_preferences_registry
from telegram.error import BadRequest, Unauthorized
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackContext, Filters, CallbackQueryHandler
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton

from app.bot import get_status, SendMessage, process_unstaking, process_stakingmode, process_mninvest, \
    process_mnwithdraw, process_send, process_sendbtc, process_otp_threshold, \
    process_otp_disable, trackmn, untrackmn, trackmnlist
from app.models import ServerMember, TGRainTask
from app.tasks.execute_tgrain import execute_tgrain
from evosbot.utils import fd, tx_logger

global_preferences = global_preferences_registry.manager()


HELP_TEXT = '''\
general commands list:
/help - This message.
/status - Show your Soverain address, wallet balance, rank, etc.
/staking `amount` - Begin staking of selected amount.
/unstaking `amount` - Stop staking of selected amount. Withdrawal up to 6 hours.
/stakingmode `mode` - Toggle staking mode (mode should be either `pool` or `individual`)
/mninvest `amount` - Invest to INSTANT SHARED masternode with automatic reinvest.
/mnwithdraw `amount` - Withdraw from masternode. Processing time no more than 24 hours!
/send `address` `amount` `2fa code (optional)` - Send coins from your wallet.
/sendbtc `address` `amount` - Withdraw BTC from bot.
/2fa `setup` - Activate 2FA.
/noinform - Toggle noinform mode
/trackmn `address` - Start masternode tracking
/untrackmn `address` - Stop masternode tracking
/trackmnlist - Show currently tracking masternodes
'''


LIKE_MESSAGES = [
    'thanks',
    'thx',
    'thankyou',
]


def get_bot():
    return Bot(global_preferences['general__telegram_bot_token'])


def status_handler(update: Update, ctx: CallbackContext):
    sm = ServerMember.from_tg_user(update.effective_user)
    update.effective_message.reply_markdown(get_status(sm, False))


def staking_handler(update: Update, ctx: CallbackContext):
    return update.effective_message.reply_markdown('Staking pool is disabled, please use mninvest instead')
    # try:
    #     amount, = ctx.args
    #     amount = Decimal(amount)
    # except:
    #     return update.effective_message.reply_markdown('Amount is either not passed or has incorrect value.\n'
    #                                                    'Usage: `/staking <amount>`')
    # sm = ServerMember.from_tg_user(update.effective_user)
    # try:
    #     process_staking(sm, amount)
    # except SendMessage as e:
    #     update.effective_message.reply_text(e.msg)


def unstaking_handler(update: Update, ctx: CallbackContext):
    try:
        amount, = ctx.args
        amount = Decimal(amount)
    except:
        return update.effective_message.reply_markdown('Amount is either not passed or has incorrect value.\n'
                                                       'Usage: `/unstaking <amount>`')
    sm = ServerMember.from_tg_user(update.effective_user)
    try:
        process_unstaking(sm, amount)
    except SendMessage as e:
        update.effective_message.reply_text(e.msg)


def stakingmode_handler(update: Update, ctx: CallbackContext):
    try:
        mode, = ctx.args
    except:
        return update.effective_message.reply_markdown('New mode is not passed.\n'
                                                       'Usage: `/stakingmode mode` '
                                                       '(mode should be either `pool` or `individual`)')
    sm = ServerMember.from_tg_user(update.effective_user)
    try:
        process_stakingmode(sm, mode)
    except SendMessage as e:
        update.effective_message.reply_markdown(e.msg)


def mninvest_handler(update: Update, ctx: CallbackContext):
    sm = ServerMember.from_tg_user(update.effective_user)
    try:
        amount, = ctx.args
        if amount == 'all':
            amount = sm.balance
        else:
            amount = Decimal(amount)
    except:
        return update.effective_message.reply_markdown('Amount is either not passed or has incorrect value.\n'
                                                       'Usage: `/mninvest <amount>`')
    try:
        process_mninvest(sm, amount)
    except SendMessage as e:
        update.effective_message.reply_text(e.msg)


def mnwithdraw_handler(update: Update, ctx: CallbackContext):
    try:
        amount, = ctx.args
        amount = Decimal(amount)
    except:
        return update.effective_message.reply_markdown('Amount is either not passed or has incorrect value.\n'
                                                       'Usage: `/mnwithdraw <amount>`')
    sm = ServerMember.from_tg_user(update.effective_user)
    try:
        process_mnwithdraw(sm, amount)
    except SendMessage as e:
        update.effective_message.reply_text(e.msg)


def send_handler(update: Update, ctx: CallbackContext):
    try:
        to, amount, *otp = ctx.args
        otp = otp[0] if otp else None
        amount = Decimal(amount)
    except:
        return update.effective_message.reply_markdown('Incorrect args were passed.\n'
                                                       'Usage: `/send address amount [2fa code]`')
    sm = ServerMember.from_tg_user(update.effective_user)
    try:
        process_send(sm, to, amount, otp, True)
    except SendMessage as e:
        update.effective_message.reply_markdown(e.msg)


def tip_handler(update: Update, ctx: CallbackContext):
    try:
        username, amount, *otp = ctx.args
        if not username.startswith('@'):
            return update.effective_message.reply_markdown('Username should start with @')
        to = ServerMember.by_tg_username(username)
        if not to:
            return update.effective_message.reply_markdown('User {} is unknown'.format(username))
        otp = otp[0] if otp else None
        amount = Decimal(amount)
    except:
        return update.effective_message.reply_markdown('Incorrect args were passed.\n'
                                                       'Usage: `/tip @username amount [2fa code]`')
    sm = ServerMember.from_tg_user(update.effective_user)
    try:
        process_send(sm, to, amount, otp, True)
    except SendMessage as e:
        update.effective_message.reply_markdown(e.msg)

    to.send_message('You were tipped {} SOVE'.format(amount))


def sendbtc_handler(update: Update, ctx: CallbackContext):
    try:
        to, amount = ctx.args
        amount = Decimal(amount)
    except:
        return update.effective_message.reply_markdown('Incorrect args were passed.\n'
                                                       'Usage: `/sendbtc address amount`')
    sm = ServerMember.from_tg_user(update.effective_user)
    try:
        process_sendbtc(sm, to, amount)
    except SendMessage as e:
        update.effective_message.reply_markdown(e.msg)


def otp_handler(update: Update, ctx: CallbackContext):
    sm = ServerMember.from_tg_user(update.effective_user)

    if not ctx.args:
        if sm.otp_active:
            update.effective_message.reply_markdown(
                'Current 2FA status: Active\n'
                'Threshold value: {} SOVE\n\n'
                'Available commands:\n'
                '`/2fa threshold <NEW_VALUE> <2fa code>` - Change threshold value\n'
                '`/2fa disable <2fa code>` - Disable 2FA'.format(fd(sm.otp_threshold))
            )
        else:
            update.effective_message.reply_markdown(
                'Current 2FA status: Inactive\n\n'
                'Available commands:\n'
                '`/2fa setup` - Activate 2FA\n'
                '`/2fa confirm <2fa code>` - After you receive a QR code, confirm activation'
                ''.format(fd(sm.otp_threshold))
            )
        return

    command = ctx.args[0]
    args = ctx.args[1:]

    if command == 'setup':
        sm.otp_secret = pyotp.random_base32()
        qr = qrcode.make(pyotp.TOTP(sm.otp_secret).provisioning_uri(sm.name, 'SOVE Bot'))
        with tempfile.TemporaryDirectory() as d:
            fpath = os.path.join(d, 'qr.png')
            qr.save(fpath)
            m = update.effective_message.reply_photo(
                open(fpath, 'rb'),
                caption='Please scan this code and use command `2fa confirm <2fa code>` '
                        'to confirm activation of 2FA\n'
                        'You also can use text secret: `{}`'.format(sm.otp_secret),
                parse_mode='markdown'
            )
            sm.otp_qr_message_id = m.message_id
            sm.save()
    elif command == 'confirm':
        try:
            otp, = args
        except:
            return update.effective_message.reply_markdown('Incorrect args were passed.\n'
                                                           'Usage: `/2fa confirm <2fa code>`')

        if sm.otp_active:
            return update.effective_message.reply_markdown('2FA is already active')
        if not sm.otp_secret:
            return update.effective_message.reply_markdown('Use `2fa setup` command first')
        if not pyotp.TOTP(sm.otp_secret).verify(otp):
            return update.effective_message.reply_markdown('Provided one-time password is invalid')
        ctx.bot.delete_message(update.effective_chat.id, sm.otp_qr_message_id)
        sm.otp_active = True
        sm.save()
        return update.effective_message.reply_markdown(
            '2FA was successfully activated.\nCurrent threshold: {} SOVE\n'
            'Use `2fa threshold <NEW_VALUE> <2fa code>` command to change it.\n\n'
            'QR code was removed for security purposes.'.format(fd(sm.otp_threshold))
        )
    elif command == 'threshold':
        try:
            otp, value = args
            value = Decimal(value)
        except:
            return update.effective_message.reply_markdown('Incorrect args were passed.\n'
                                                           'Usage: `/2fa threshold value <2fa code>`')

        try:
            process_otp_threshold(sm, value, otp)
        except SendMessage as e:
            update.effective_message.reply_markdown(e.msg)
    elif command == 'disable':
        try:
            otp, = args
        except:
            return update.effective_message.reply_markdown('Incorrect args were passed.\n'
                                                           'Usage: `/2fa disable <2fa code>`')

        try:
            process_otp_disable(sm, otp)
        except SendMessage as e:
            update.effective_message.reply_markdown(e.msg)


def help_handler(update: Update, ctx: CallbackContext):
    update.effective_message.reply_markdown(HELP_TEXT)


def noinform_handler(update: Update, ctx: CallbackContext):
    sm = ServerMember.from_tg_user(update.effective_user)
    sm.noinform = not sm.noinform
    sm.save()
    update.effective_message.reply_text('Noinform mode was {}'.format('enabled' if sm.noinform else 'disabled'))


def rain_handler(update: Update, ctx: CallbackContext):
    sm = ServerMember.from_tg_user(update.effective_user)
    try:
        users_cnt, minutes, amount, *rest = ctx.args
        chat_id = int(rest[0]) if rest else global_preferences['general__telegram_chat_id']
        users_cnt = int(users_cnt)
        minutes = int(minutes)
        amount = Decimal(amount)

        if not (0 < users_cnt <= 50):
            return update.effective_message.reply_text('Users count should be in interval 1..50')
        if minutes <= 0:
            return update.effective_message.reply_text('Duration should be positive')
        if amount > sm.balance:
            return update.effective_message.reply_text('Insufficient funds')
    except:
        return update.effective_message.reply_markdown('Incorrect args were passed.\n'
                                                       'Usage: `/rain users_cnt minutes amount [chat_id]`')

    try:
        ctx.bot.get_chat_members_count(chat_id)
    except (BadRequest, Unauthorized):
        return update.effective_message.reply_text('Bot is not added to the specified chat')

    with transaction.atomic():
        time = now() + timedelta(minutes=minutes)
        t = TGRainTask.objects.create(member=sm, users_cnt=users_cnt, amount=amount, execute_at=time, _chat_id=chat_id)
        markup = InlineKeyboardMarkup([[InlineKeyboardButton('Enter', callback_data='rain_part {}'.format(t.pk))]])
        msg = t.render_info()
        m = ctx.bot.send_message(chat_id, msg, 'markdown', reply_markup=markup)
        t.message_id = m.message_id
        t.save()
        sm.balance -= amount
        sm.save()
        tx_logger.warning('TGRAIN_CREATE,{},-{:.8f}'.format(sm, amount))
        execute_tgrain.apply_async(args=(t.pk,), eta=time)


def rain_enter_handler(update: Update, ctx: CallbackContext):
    sm = ServerMember.from_tg_user(update.effective_user)
    _, rain_id = update.callback_query.data.split()
    with transaction.atomic():
        try:
            t = TGRainTask.objects.filter(finished=False).select_for_update().get(pk=rain_id)  # type: TGRainTask
        except TGRainTask.DoesNotExist:
            return update.callback_query.answer()
        users = t.users.split('|')
        uid = str(update.effective_user.id)
        if str(uid) in users:
            users.remove(uid)
            update.callback_query.answer('You no longer participate in this rain')
        else:
            users.append(uid)
            update.callback_query.answer('Now you participate in this rain')
        t.users = '|'.join(users)
        t.save()
        markup = InlineKeyboardMarkup([[InlineKeyboardButton('Enter', callback_data='rain_part {}'.format(t.pk))]])
        update.callback_query.edit_message_text(t.render_info(), reply_markup=markup, parse_mode='markdown')


def trackmn_handler(update: Update, ctx: CallbackContext):
    try:
        addr = ctx.args
    except:
        return update.effective_message.reply_markdown('Incorrect args were passed.\n'
                                                       'Usage: `/trackmn address`')
    sm = ServerMember.from_tg_user(update.effective_user)
    try:
        trackmn(sm, addr)
    except SendMessage as e:
        update.effective_message.reply_markdown(e.msg)


def untrackmn_handler(update: Update, ctx: CallbackContext):
    try:
        addr = ctx.args
    except:
        return update.effective_message.reply_markdown('Incorrect args were passed.\n'
                                                       'Usage: `/untrackmn address`')
    sm = ServerMember.from_tg_user(update.effective_user)
    try:
        untrackmn(sm, addr)
    except SendMessage as e:
        update.effective_message.reply_markdown(e.msg)


def trackmnlist_handler(update: Update, ctx: CallbackContext):
    sm = ServerMember.from_tg_user(update.effective_user)
    try:
        trackmnlist(sm)
    except SendMessage as e:
        update.effective_message.reply_markdown(e.msg)


def like_handler(update: Update, ctx: CallbackContext):
    author = ServerMember.from_tg_user(update.effective_user)
    if author.last_like and now() - author.last_like < timedelta(hours=1):
        return update.effective_message.reply_markdown('You liked someone less than an hour ago')

    if not author.rank:
        return update.effective_message.reply_markdown('Your rank is Brand New, so you cannot like, please wait until your rank is increased')

    sm = ServerMember.from_tg_user(update.effective_message.reply_to_message.from_user)
    if not sm.rank:
        return update.effective_message.reply_markdown('You cannot like users with Brand New rank')
    if sm == author:
        return update.effective_message.reply_markdown('You cannot like your own messages')

    sm.xp += Decimal('.25')
    sm.activity_counter += 1
    sm.save()
    author.last_like = now()
    author.save()
    message = 'User XP: {sm.xp}\n' \
              'User activity: {sm.activity_counter} minutes\n' \
              'User rank: {sm.rank_display}\n'.format(sm=sm)
    update.effective_message.reply_markdown(message)


def message_handler(update: Update, ctx: CallbackContext):
    sm = ServerMember.from_tg_user(update.effective_user)
    if len(update.effective_message.text) >= 50 and \
            (not sm.last_message or now() - sm.last_message > timedelta(seconds=60 + randint(0, 60))):
        sm.xp += 1
        sm.last_message = now()
        sm.save()

    if update.effective_message.reply_to_message:
        text = re.sub(r'\W', '', update.effective_message.text).lower()
        if text in LIKE_MESSAGES:
            like_handler(update, ctx)


def get_updater():
    updater = Updater(global_preferences['general__telegram_bot_token'], use_context=True)
    updater.dispatcher.add_handler(CommandHandler('start', status_handler, Filters.private))
    updater.dispatcher.add_handler(CommandHandler('status', status_handler, Filters.private))
    updater.dispatcher.add_handler(CommandHandler('staking', staking_handler, Filters.private))
    updater.dispatcher.add_handler(CommandHandler('unstaking', unstaking_handler, Filters.private))
    updater.dispatcher.add_handler(CommandHandler('stakingmode', stakingmode_handler, Filters.private))
    updater.dispatcher.add_handler(CommandHandler('mninvest', mninvest_handler, Filters.private))
    updater.dispatcher.add_handler(CommandHandler('mnwithdraw', mnwithdraw_handler, Filters.private))
    updater.dispatcher.add_handler(CommandHandler('send', send_handler, Filters.private))
    updater.dispatcher.add_handler(CommandHandler('tip', tip_handler, Filters.private))
    updater.dispatcher.add_handler(CommandHandler('sendbtc', sendbtc_handler, Filters.private))
    updater.dispatcher.add_handler(CommandHandler('2fa', otp_handler, Filters.private))
    updater.dispatcher.add_handler(CommandHandler('help', help_handler, Filters.private))
    updater.dispatcher.add_handler(CommandHandler('noinform', noinform_handler, Filters.private))
    updater.dispatcher.add_handler(CommandHandler('rain', rain_handler, Filters.private))
    updater.dispatcher.add_handler(CommandHandler('trackmn', trackmn_handler, Filters.private))
    updater.dispatcher.add_handler(CommandHandler('untrackmn', untrackmn_handler, Filters.private))
    updater.dispatcher.add_handler(CommandHandler('trackmnlist', trackmnlist_handler, Filters.private))
    updater.dispatcher.add_handler(CommandHandler('chatid',
                                                  lambda a, b: a.effective_message.reply_text(str(a.effective_chat.id))))
    updater.dispatcher.add_handler(CallbackQueryHandler(rain_enter_handler, pattern=r'^rain_part \d+$'))
    updater.dispatcher.add_handler(CommandHandler('like', like_handler, Filters.group & Filters.reply))
    updater.dispatcher.add_handler(MessageHandler(Filters.text, message_handler))

    return updater


