from celery import shared_task
from celery_once import QueueOnce
from django.db import transaction

from app.models import ServerMember
from evosbot.celery import app
from evosbot.utils import client, bitcoin_client, tx_logger


@app.task(name='app.tasks.check_deposits', base=QueueOnce, once={'graceful': True})
def check_deposits():
    # update unconfirmed balances
    for balance in client.received_by_address(0):
        ServerMember.objects.filter(_wallet_address=balance['address']) \
            .update(received_unconfirmed=balance['amount'])

    # update confirmed balances
    for balance in client.received_by_address():
        with transaction.atomic():
            member = ServerMember.objects.filter(_wallet_address=balance['address']).select_for_update().first()  # type: ServerMember
            if not member:
                continue
            if balance['amount'] > member.received:
                delta = balance['amount'] - member.received
                member.balance += delta
                member.received = balance['amount']
                member.save(update_fields=('balance', 'received',))
                tx_logger.warning('DEPOSIT,{},+{:.8f}'.format(member, delta))

    # BITCOIN
    # update unconfirmed balances
    for balance in bitcoin_client.received_by_address(0):
        ServerMember.objects.filter(_bitcoin_wallet_address=balance['address']) \
            .update(bitcoin_received_unconfirmed=balance['amount'])

    # update confirmed balances
    for balance in bitcoin_client.received_by_address():
        with transaction.atomic():
            member = ServerMember.objects.filter(_bitcoin_wallet_address=balance['address']).select_for_update().first()  # type: ServerMember
            if not member:
                continue
            if balance['amount'] > member.bitcoin_received:
                delta = balance['amount'] - member.bitcoin_received
                member.bitcoin_balance += delta
                member.bitcoin_received = balance['amount']
                member.save(update_fields=('bitcoin_balance', 'bitcoin_received',))
