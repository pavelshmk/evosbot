import logging
import math
import traceback

import requests
from celery_once import QueueOnce
from django.db import transaction
from django.utils.timezone import now
from dynamic_preferences.registries import global_preferences_registry

from app.models import MasternodeWithdraw, Masternode
from evosbot.celery import app
from evosbot.utils import masternode_client, masternode_address, get_masternode_price, RPCClient

global_preferences = global_preferences_registry.manager()


@app.task(name='app.tasks.process_mn_withdraws', base=QueueOnce, once={'graceful': True})
def process_mn_withdraws():
    if global_preferences['internal__masternode_lock']:
        return

    try:
        global_preferences['internal__masternode_lock'] = True
        for mnw in MasternodeWithdraw.objects.filter(fulfilled=False, fulfill_at__lte=now()):  # type: MasternodeWithdraw
            try:
                sm = mnw.member

                masternode_price = get_masternode_price()
                masternode_txids = Masternode.objects.filter(active=True).values_list('output_txid', 'output_idx')
                locked = [tx for tx in masternode_client.api.listlockunspent() if (tx['txid'], tx['vout']) not in masternode_txids]
                for l in locked:
                    tx = masternode_client.api.decoderawtransaction(masternode_client.api.getrawtransaction(l['txid']))
                    l['amount'] = tx['vout'][l['vout']]['value']

                unspents = masternode_client.api.listunspent(0)
                unspents_sum = sum(b['amount'] for b in locked + unspents)
                if unspents_sum < mnw.amount:
                    masternode_client.api.lockunspent(False, unspents)
                    masternode_client.api.masternode('outputs')

                    if masternode_client.api.getbalance() - masternode_price * len(masternode_txids) < mnw.amount:
                        sid = transaction.savepoint()
                        # unlock funds
                        active_masternodes = list(Masternode.objects.filter(active=True).order_by('-weight'))[:-1]
                        if mnw.amount >= unspents_sum + masternode_price * len(active_masternodes):
                            logging.warning('Not enough funds')
                            continue
                        for mn in active_masternodes:  # type: Masternode
                            locked = [{'txid': mn.output_txid, 'vout': mn.output_idx, 'amount': masternode_price}] + locked
                            unspents_sum += masternode_price
                            mn.active = False
                            mn.output_txid = mn.output_txid = None
                            mn.save()
                            if unspents_sum >= mnw.amount:
                                break
                        r1 = requests.post(global_preferences['general__masternode_service_uri'] + '/config', json={
                            'content': Masternode.generate_config(),
                        })
                        r2 = requests.post(global_preferences['general__masternode_service_uri'] + '/reload')
                        if r1.text != 'OK' or r2.text != 'OK':
                            requests.post(global_preferences['general__masternode_service_uri'] + '/config', json={
                                'content': Masternode.generate_config(),
                            })
                            transaction.savepoint_rollback(sid)
                    return

                fee = masternode_client.estimate_fee(1)
                inputs = []
                inputs_sum = 0
                for uo in locked + unspents:
                    inputs.append({'txid': uo['txid'], 'vout': uo['vout']})
                    inputs_sum += uo['amount']
                    if inputs_sum >= mnw.amount:
                        break
                else:
                    raise RuntimeError('Request #{}: Not enough funds on the wallet'.format(mnw.pk))

                outputs = {sm.wallet_address: mnw.amount}
                if inputs_sum > mnw.amount:
                    outputs[masternode_address()] = inputs_sum - mnw.amount

                estimate_tx = masternode_client.api.createrawtransaction(inputs, outputs)
                estimate_tx = masternode_client.api.signrawtransaction(estimate_tx)
                fee *= math.ceil(len(bytes.fromhex(estimate_tx['hex'])) / 1024 + 1)

                outputs[sm.wallet_address] -= fee
                tx = masternode_client.api.createrawtransaction(inputs, outputs)
                tx = masternode_client.api.signrawtransaction(tx)
                try:
                    txid = masternode_client.api.sendrawtransaction(tx['hex'])
                except RPCClient.RPCException as e:
                    if e.code in [-26, -25]:
                        masternode_client.api.reservebalance(True, masternode_client.api.getbalance())
                        masternode_client.api.lockunspent(True, locked)
                        masternode_client.api.masternode('outputs')
                        masternode_client.api.reservebalance(False)
                        logging.error('process_mn_withdraws: bad-txns-inputs-spent ({}), unlocked'.format(e.code))
                        return
                    raise
                sm.send_message('{} SOVE was withdrawn from masternode\ntxid: `{}`'.format(mnw.amount, txid))
                mnw.fulfilled = True
                mnw.save()
                masternode_client.api.reservebalance(True, masternode_client.api.getbalance())
                masternode_client.api.lockunspent(True, locked)
                masternode_client.api.masternode('outputs')
                masternode_client.api.reservebalance(False)
            except:
                traceback.print_exc()
    finally:
        global_preferences['internal__masternode_lock'] = False
