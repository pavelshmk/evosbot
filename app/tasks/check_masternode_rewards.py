import logging
from celery_once import QueueOnce
from django.db import transaction
from dynamic_preferences.registries import global_preferences_registry

from app.models import ServerMember, MasternodeBalanceLog
from evosbot.celery import app
from evosbot.utils import masternode_client, send_discord_message, fd, get_masternode_price

global_preferences = global_preferences_registry.manager()


@app.task(name='app.tasks.check_masternode_rewards', base=QueueOnce, once={'graceful': True})
def check_masternode_rewards():
    masternode_price = get_masternode_price()
    total_deposit = (masternode_client.api.getbalance() // masternode_price) * masternode_price

    if not total_deposit:
        return

    lst = masternode_client.api.listsinceblock(global_preferences['internal__last_masternode_block'])
    txs = filter(lambda tx: tx.get('confirmations', 0) >= 0, lst['transactions'])
    generated_transactions = [tx for tx in txs if tx.get('generated') and tx['category'] == 'receive']

    vouts_max = {}
    pos_txids = set()
    mn_rewards = 0
    min_confirmations = 999999999
    for tx in generated_transactions:
        if 0 < tx['confirmations'] < min_confirmations:
            global_preferences['internal__last_masternode_block'] = tx['blockhash']
            min_confirmations = tx['confirmations']

        if tx['vout'] < 1:
            continue
        if tx['txid'] not in vouts_max:
            txhex = masternode_client.api.getrawtransaction(tx['txid'])
            decoded = masternode_client.api.decoderawtransaction(txhex)
            vouts_max[tx['txid']] = max(vout['n'] for vout in decoded['vout'])
        if tx['vout'] == vouts_max[tx['txid']]:
            mn_rewards += tx['amount']
        else:
            pos_txids.add(tx['txid'])

    pos_rewards = 0
    for txid in pos_txids:
        tx = masternode_client.api.gettransaction(txid)
        pos_rewards += tx['amount'] + tx['fee']

    total_rewards = mn_rewards + pos_rewards

    if not total_rewards:
        return

    members = ServerMember.objects.filter(masternode_balance__gt=0)

    summ = 0
    trew = 0
    with transaction.atomic():
        for sm in members.select_for_update():
            reward = sm.masternode_balance / total_deposit * total_rewards
            trew += reward
            sm.masternode_balance += reward
            summ += sm.masternode_balance
            sm.save(update_fields=('masternode_balance',))
            sm.update_investor_role()
            MasternodeBalanceLog.objects.create(member=sm, balance=sm.masternode_balance, delta=reward)

    send_discord_message(global_preferences['general__reward_report_channel_id'],
                         'Masternode rewards: {}\n'
                         'Masternode staking rewards: {}\n'
                         'Distributed among {} users'.format(fd(mn_rewards), fd(pos_rewards), members.count()))

    logging.warning('sharedmn USERS depo summ: {} wallet balance: {} diff: {} total_rewards: {} distributed: {}'.format(summ, masternode_client.api.getbalance(), masternode_client.api.getbalance()-summ, total_rewards, trew))
