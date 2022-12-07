import logging
import os
import tempfile
import traceback
from datetime import timedelta
from decimal import Decimal
from random import randint
from typing import Union

import pyotp
import qrcode
from django.db import transaction
from django.utils.timezone import now
from dynamic_preferences.registries import global_preferences_registry

from app.models import ServerMember, Unstaking, MNInvestTask, MasternodeWithdraw, MasternodeBalanceLog, \
    TrackedMasternode
from evosbot.utils import client, fd, staking_pool_address, tx_logger, staking_client, masternode_client, bitcoin_client

global_preferences = global_preferences_registry.manager()


class SendMessage(RuntimeError):
    def __init__(self, msg, *args):
        self.msg = msg
        super().__init__(*args)


def get_status(sm: ServerMember, discord=True):
    staking_balance = '{:.8f}'.format(max(0, sm.staking_balance))
    if not sm.is_staking_pool:
        staking_balance += ' ({sm.staking_unspent_amount:.8f} unstakable)'.format(sm=sm)
    unstaking_pending = 'Unstaking pending: {sm.pending_unstaking:.8f} SOVE\n'.format(
        sm=sm) if sm.is_staking_pool else ''
    message = 'Current XP: {sm.xp}\n' \
              'Current activity: {sm.activity_counter} minutes\n' \
              'Current rank: {sm.rank_display}\n'
    message += 'Wallet address: `{sm.wallet_address}`\n' \
               'Wallet balance: {sm.balance:.8f} SOVE\n' \
               'Unconfirmed balance: {sm.unconfirmed_balance:.8f} SOVE\n\n' \
               'Staking balance: {sb} SOVE\n' \
               '{up}' \
               'Staking mode: {staking_mode}\n\n' \
               'Masternode invest amount: {sm.masternode_balance:.8f} SOVE\n' \
               'Pending masternode withdraw: {sm.pending_mn_withdraw:.8f} SOVE\n\n' \
               'Bitcoin address: `{sm.bitcoin_wallet_address}`\n' \
               'Bitcoin balance: {sm.bitcoin_balance:.8f}\n' \
               'Bitcoin unconfirmed balance: {sm.bitcoin_unconfirmed_balance:.8f}'
    message = message.format(
        sm=sm,
        staking_mode='pool' if sm.is_staking_pool else 'individual',
        sb=staking_balance,
        up=unstaking_pending
    )
    return message


def process_staking(sm: ServerMember, amount: Decimal):
    with transaction.atomic():
        sm = ServerMember.objects.select_for_update().get(pk=sm.pk)
        if sm.balance < amount:
            raise SendMessage('Insufficient funds')
        if amount <= client.minimal_spend():
            raise SendMessage('Amount should be more than {}'.format(fd(client.minimal_spend())))
        amount_without_fee = amount - global_preferences['general__transaction_commission']
        try:
            if sm.is_staking_pool:
                txid = client.send_funds(staking_pool_address(), amount_without_fee)
                sm.staking_pool_amount += amount_without_fee
            else:
                txid = client.send_funds(sm.staking_wallet_address, amount_without_fee)
        except RuntimeError:
            raise SendMessage('Operation is currently unavailable, please try later')
        sm.balance -= amount
        sm.save()
        tx_logger.warning('STAKING,{},-{:.8f}'.format(sm, amount))
    raise SendMessage('Started staking of {}'.format(fd(amount)))


def process_unstaking(sm: ServerMember, amount: Decimal):
    if amount <= staking_client.minimal_spend():
        raise SendMessage('Amount should be more than {}'.format(fd(staking_client.minimal_spend())))
    if not sm.is_staking_pool:
        unspents = sm.staking_unspent(0)
        outputs = {}
        if sm.staking_unspent_amount < amount:
            raise SendMessage('Insufficient funds')
        elif sm.staking_unspent_amount > amount:
            outputs[sm.staking_wallet_address] = sm.staking_unspent_amount - amount
        staking_client.send_funds_multiple(outputs, unspents, sm.wallet_address)
        raise SendMessage('{} were unstaked'.format(fd(amount)))
    else:
        if sm.staking_balance < amount:
            raise SendMessage('Insufficient funds')
        Unstaking.objects.create(member=sm, amount=amount, fulfill_at=now() + timedelta(hours=randint(2, 6)))
        raise SendMessage('Unstaking request for {} was created'.format(fd(amount)))


def process_stakingmode(sm: ServerMember, mode: str):
    if mode not in ['pool', 'individual']:
        raise SendMessage('Select either `pool` or `individual`')
    with transaction.atomic():
        sm = ServerMember.objects.select_for_update().get(pk=sm.pk)
        if (sm.is_staking_pool and sm.staking_pool_amount or
                not sm.is_staking_pool and (sm.staking_balance or sm.pending_unstaking)):
            raise SendMessage('Could not toggle mode when there are staking coins or pending unstakings')
        sm.is_staking_pool = mode == 'pool'
        sm.save()
    raise SendMessage('Staking mode was toggled')


def process_mninvest(sm: ServerMember, amount: Decimal):
    with transaction.atomic():
        pr = MNInvestTask.objects.filter(member=sm, processed=False).first()
        if pr:
            raise SendMessage('You already have a pending invest request for {} SOVE'.format(fd(pr.amount)))
        sm = ServerMember.objects.select_for_update().get(pk=sm.pk)
        if sm.balance < amount:
            raise SendMessage('Insufficient funds')
        if amount <= client.minimal_spend():
            raise SendMessage('Amount should be more than {} SOVE'.format(fd(client.minimal_spend())))
        stack_median = global_preferences['internal__stack_median']
        if sm.masternode_balance < 2 and amount < 10:
            raise SendMessage('Minimal invest amount is {} SOVE'.format(fd(10)))
        amount_without_fee = amount - global_preferences['general__transaction_commission']
        sm.balance -= amount
        sm.save()
        tx_logger.warning('MNINVEST,{},-{:.8f}'.format(sm, amount))
        MNInvestTask.objects.create(member=sm, amount=amount, amount_without_fee=amount_without_fee)
    raise SendMessage('Invest request was queued')


def process_mnwithdraw(sm: ServerMember, amount: Decimal):
    with transaction.atomic():
        sm = ServerMember.objects.select_for_update().get(pk=sm.pk)
        if sm.masternode_balance < amount:
            raise SendMessage('Insufficient funds')
        if amount <= masternode_client.minimal_spend():
            raise SendMessage('Amount should be more than {}'.format(fd(masternode_client.minimal_spend())))
        MasternodeWithdraw.objects.create(
            member=sm,
            amount=amount,
            fulfill_at=now() + timedelta(hours=randint(6, 24))
        )
        sm.masternode_balance -= amount
        sm.save()
        MasternodeBalanceLog.objects.create(member=sm, balance=sm.masternode_balance, delta=-amount)
    raise SendMessage('Withdraw from masternode request for {} was created'.format(fd(amount)))


def process_send(sm: ServerMember, to: Union[ServerMember, str], amount: Decimal, otp: str = None, tg=False):
    with transaction.atomic():
        if sm.otp_active and amount >= sm.otp_threshold and not pyotp.TOTP(sm.otp_secret).verify(otp):
            if tg:
                raise SendMessage('One-time password is either incorrect or not provided.\n'
                                  'Usage: `/send <wallet address> amount [2fa code]`')
            else:
                raise SendMessage('One-time password is either incorrect or not provided.\n'
                                  'Usage: `$send <@mention or wallet address> amount [2fa code]`')
        logging.warning('checked otp')
        sm = ServerMember.objects.select_for_update().get(pk=sm.pk)
        if sm.balance < amount:
            raise SendMessage('Insufficient funds')
        logging.warning('checked balance')
        if amount <= client.minimal_spend():
            raise SendMessage('Amount should be more than {}'.format(fd(client.minimal_spend())))
        logging.warning('checked minimal limit')
        if isinstance(to, ServerMember):
            sm.balance -= amount
            sm.save()
            tx_logger.warning('SEND,{},-{:.8f}'.format(sm, amount))
            to_member = ServerMember.objects.select_for_update().get(pk=to.pk)
            to_member.balance += amount
            to_member.save()
            tx_logger.warning('SEND,{},+{:.8f}'.format(to_member, amount))
            if tg:
                result = '{} SOVE sent to @{}\'s wallet'.format(fd(amount), to.username)
            else:
                result = '{} SOVE sent to <@{}>\'s wallet'.format(fd(amount), to.id)
        else:
            logging.warning('validating address')
            if not client.validate_address(to):
                raise SendMessage('Specified address is invalid')
            try:
                logging.warning('sending funds')
                txid = client.send_funds(to, amount - global_preferences['general__transaction_commission'])
                logging.warning('changing balance')
                sm.balance -= amount
                sm.save()
                tx_logger.warning('SEND,{},-{:.8f},{}'.format(sm, amount, to))
                result = '{} SOVE sent to `{}`\nTXID: `{}`'.format(fd(amount), to, txid)
            except RuntimeError:
                traceback.print_exc()
                raise SendMessage('Operation is currently unavailable, please try later')
            except:
                traceback.print_exc()
    raise SendMessage(result)


def process_sendbtc(sm: ServerMember, address: str, amount: Decimal):
    with transaction.atomic():
        sm = ServerMember.objects.select_for_update().get(pk=sm.pk)
        if sm.bitcoin_balance < amount:
            raise SendMessage('Insufficient balance')
        if not bitcoin_client.validate_address(address):
            raise SendMessage('Invalid address')
        try:
            txid = bitcoin_client.api.sendtoaddress(address, amount, None, None, True)
        except:
            raise SendMessage('Operation is currently unavailable, please try later')
        sm.bitcoin_balance -= amount
        sm.save()
    raise SendMessage('txid: `{}`'.format(txid))


def process_otp_setup(sm: ServerMember, send_message):
    if sm.otp_active:
        raise SendMessage('2FA is already active')
    sm.otp_secret = pyotp.random_base32()
    qr = qrcode.make(pyotp.TOTP(sm.otp_secret).provisioning_uri(sm.name, 'SOVE Bot'))
    with tempfile.TemporaryDirectory() as d:
        fpath = os.path.join(d, 'qr.png')
        qr.save(fpath)
        mid = send_message('Please scan this code and use command `2fa confirm <2fa code>` '
                           'to confirm activation of 2FA\n'
                           'You also can use text secret: `{}`'.format(sm.otp_secret),
                           fpath)
        sm.otp_qr_message_id = mid
        sm.save()


def process_otp_confirm(sm: ServerMember, otp: str, delete_message):
    if sm.otp_active:
        raise SendMessage('2FA is already active')
    if not sm.otp_secret:
        raise SendMessage('Use `2fa setup` command first')
    if not pyotp.TOTP(sm.otp_secret).verify(otp):
        raise SendMessage('Provided one-time password is invalid')
    delete_message(sm.otp_qr_message_id)
    sm.otp_active = True
    sm.save()
    raise SendMessage('2FA was successfully activated.\nCurrent threshold: {} SOVE\n'
                      'Use `2fa threshold <NEW_VALUE> <2fa code>` command to change it.\n\n'
                      'QR code was removed for security purposes.'.format(fd(sm.otp_threshold)))


def process_otp_threshold(sm: ServerMember, value: Decimal, otp: str):
    if not sm.otp_active:
        raise SendMessage('2FA is not active, please use `2fa setup` command first')
    if not pyotp.TOTP(sm.otp_secret).verify(otp):
        raise SendMessage('Provided one-time password is invalid')
    if value < 0:
        raise SendMessage('New threshold value should be positive')
    sm.otp_threshold = value
    sm.save()
    raise SendMessage('2FA threshold was successfully changed')


def process_otp_disable(sm: ServerMember, otp: str):
    if not sm.otp_active:
        raise SendMessage('2FA is not active, please use `2fa setup` command first')
    if not pyotp.TOTP(sm.otp_secret).verify(otp):
        raise SendMessage('Provided one-time password is invalid')
    sm.otp_secret = None
    sm.otp_active = False
    sm.save()
    raise SendMessage('2FA was successfully disabled')


def trackmn(sm: ServerMember, addr: str):
    if sm.tracked_masternodes.count() == 20:
        raise SendMessage('You cannot have more than 20 tracked masternodes')
    if sm.tracked_masternodes.filter(addr=addr).count():
        raise SendMessage('You are already tracking this masternode')
    mns = {m['addr']: m for m in client.api.masternode('list')}
    mn = mns.get(addr)
    if not mn:
        raise SendMessage('Masternode was not found')
    TrackedMasternode.objects.create(member=sm, addr=addr, last_check_status=mn['status'])
    raise SendMessage('Added masternode to tracking, current status: {}'.format(mn['status']))


def untrackmn(sm: ServerMember, addr: str):
    mn = sm.tracked_masternodes.filter(addr=addr).first()
    if not mn:
        raise SendMessage('You are not tracking specified masternode')
    mn.delete()
    raise SendMessage('Stopped tracking masternode')


def trackmnlist(sm: ServerMember):
    mns = sm.tracked_masternodes.all()
    if not mns.count():
        raise SendMessage('You have no tracked masternodes')
    result = []
    for mn in mns:
        result.append('- {}, last status: {}'.format(mn.addr, mn.last_check_status))

    raise SendMessage('\n'.join(result))
