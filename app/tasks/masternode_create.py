import logging
from decimal import Decimal
from time import sleep

import requests
from celery_once import QueueOnce
from dynamic_preferences.registries import global_preferences_registry

from app.models import Masternode
from evosbot.celery import app
from evosbot.utils import masternode_client, get_masternode_price, masternode_address, RPCClient

global_preferences = global_preferences_registry.manager()
global_preferences['internal__masternode_lock'] = False


@app.task(name='app.tasks.masternode_create', base=QueueOnce, once={'graceful': True})
def masternode_create():
    if global_preferences['internal__masternode_lock']:
        return

    global_preferences['internal__masternode_lock'] = True
    try:
        mn = Masternode.objects.filter(active=False).first()  # type: Masternode
        if not mn:
            logging.warning('No unused masternodes')
            return

        masternode_price = get_masternode_price()

        masternode_txids = Masternode.objects.filter(active=True).values_list('output_txid', 'output_idx')
        locked = [tx for tx in masternode_client.api.listlockunspent() if (tx['txid'], tx['vout']) not in masternode_txids]
        for l in locked:
            tx = masternode_client.api.decoderawtransaction(masternode_client.api.getrawtransaction(l['txid']))
            l['amount'] = tx['vout'][l['vout']]['value']
        unspent = [tx for tx in masternode_client.api.listunspent(0) if (tx['txid'], tx['vout']) not in masternode_txids]
        sum_unspent = sum(u['amount'] for u in locked + unspent)

        if sum_unspent <= masternode_price * Decimal('1.001'):
            if masternode_price * Decimal('1.001') <= masternode_client.api.getbalance() - masternode_price * len(masternode_txids):
                masternode_client.api.lockunspent(False, unspent)
                masternode_client.api.masternode('outputs')
            return

        new_address = masternode_client.api.getnewaddress()
        try:
            txid = masternode_client.send_funds_multiple({new_address: masternode_price}, locked + unspent,
                                                         masternode_address())
        except RPCClient.RPCException as e:
            if e.code in [-26, -25]:
                masternode_client.api.reservebalance(True, masternode_client.api.getbalance())
                masternode_client.api.lockunspent(True, locked)
                masternode_client.api.masternode('outputs')
                masternode_client.api.reservebalance(False)
                logging.error('masternode_create: bad-txns-inputs-spent, unlocked')
                return
            raise
        masternode_client.api.reservebalance(True, masternode_client.api.getbalance())
        masternode_client.api.lockunspent(True, locked)
        masternode_client.api.masternode('outputs')
        masternode_client.api.reservebalance(False)
        sleep(30)
        try:
            outputidx = {o['txhash']: o for o in masternode_client.api.masternode('outputs')}[txid]['outputidx']
        except KeyError:
            logging.warning('mn outputs')
            logging.warning(masternode_client.api.masternode('outputs'))
            raise RuntimeError('Cannot find outputidx')

        mn.output_txid = txid
        mn.output_idx = outputidx
        mn.active = True
        mn.save()

        r = requests.post(global_preferences['general__masternode_service_uri'] + '/config', json={
            'content': Masternode.generate_config(),
        })
        if r.text == 'OK':
            current_block = masternode_client.api.getblockcount()
            r = requests.post(global_preferences['general__masternode_service_uri'] + '/reload')
            if r.text == 'OK':
                while True:
                    try:
                        masternode_client.api.getblockcount()
                        break
                    except:
                        sleep(5)
                while masternode_client.api.getblockcount() - current_block < 15:
                    print('Diff is', masternode_client.api.getblockcount() - current_block, 'blocks')
                    sleep(60)
                result = masternode_client.api.startmasternode('alias', '0', mn.alias)
                print(result)
    finally:
        global_preferences['internal__masternode_lock'] = False
