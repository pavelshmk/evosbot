from celery import shared_task
from celery_once import QueueOnce
from django.db import transaction
from django.db.models import Sum
from dynamic_preferences.registries import global_preferences_registry

from app.models import ServerMember
from evosbot.celery import app
from evosbot.utils import staking_pool_client, send_discord_message, fd

global_preferences = global_preferences_registry.manager()


@app.task(name='app.tasks.check_staking_pool_rewards', base=QueueOnce, once={'graceful': True})
def check_staking_pool_rewards():
    result = staking_pool_client.api.listsinceblock(global_preferences['internal__last_staking_pool_block'])
    txs = result['transactions']

    txids = set()
    min_confirmations = 999999999
    for tx in txs:
        if tx.get('generated'):
            confirmations = tx.get('confirmations', -1)
            if confirmations > 0:
                txids.add(tx['txid'])
                if confirmations < min_confirmations:
                    global_preferences['internal__last_staking_pool_block'] = tx['blockhash']
                    min_confirmations = confirmations
    reward = 0
    for txid in txids:
        txinfo = staking_pool_client.api.gettransaction(txid)
        reward += txinfo['amount'] + txinfo['fee']
    if not reward:
        return
    pool_members = ServerMember.objects.filter(staking_pool_amount__gt=0)\
        .exclude(unstakings__isnull=False, unstakings__fulfilled=False)
    pool_sum = pool_members.aggregate(pool_sum=Sum('staking_pool_amount'))['pool_sum'] or 0

    with transaction.atomic():
        for member in pool_members.select_for_update():
            part = member.staking_pool_amount / pool_sum
            member.staking_pool_amount += reward * part
            member.save(update_fields=('staking_pool_amount',))
            member.update_investor_role()

    send_discord_message(global_preferences['general__reward_report_channel_id'],
                         'Staking pool rewards: {}\n'
                         'Distributed among {} users'.format(fd(reward), pool_members.count()))
