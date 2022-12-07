import logging
import math
import traceback

from celery_once import QueueOnce
from django.utils.timezone import now

from app.models import Unstaking
from evosbot.celery import app
from evosbot.utils import staking_pool_client, staking_pool_address, RPCClient


@app.task(name='app.tasks.process_unstaking', base=QueueOnce, once={'graceful': True})
def process_unstaking():
    spc = staking_pool_client
    for u in Unstaking.objects.filter(fulfilled=False, fulfill_at__lte=now()):  # type: Unstaking
        try:
            sm = u.member
            if sm.is_staking_pool:
                locked = spc.api.listlockunspent()
                for l in locked:
                    tx = spc.api.decoderawtransaction(spc.api.getrawtransaction(l['txid']))
                    l['amount'] = tx['vout'][l['vout']]['value']

                unspents = spc.api.listunspent(0)
                unspents_sum = sum(b['amount'] for b in locked + unspents)
                if unspents_sum < u.amount:
                    spc.api.lockunspent(False, unspents)
                    return

                fee = spc.estimate_fee(1)
                inputs = []
                inputs_sum = 0
                for uo in locked + unspents:
                    inputs.append({'txid': uo['txid'], 'vout': uo['vout']})
                    inputs_sum += uo['amount']
                    if inputs_sum >= u.amount:
                        break
                else:
                    raise RuntimeError('Request #{}: Not enough funds on the wallet'.format(u.pk))

                outputs = {sm.wallet_address: u.amount}
                if inputs_sum > u.amount:
                    outputs[staking_pool_address()] = inputs_sum - u.amount

                estimate_tx = spc.api.createrawtransaction(inputs, outputs)
                estimate_tx = spc.api.signrawtransaction(estimate_tx)
                fee *= math.ceil(len(bytes.fromhex(estimate_tx['hex'])) / 1024 + 1)

                outputs[sm.wallet_address] -= fee
                tx = spc.api.createrawtransaction(inputs, outputs)
                tx = spc.api.signrawtransaction(tx)
                try:
                    txid = spc.api.sendrawtransaction(tx['hex'])
                except RPCClient.RPCException as e:
                    if e.code in [-26, -25]:
                        spc.api.lockunspent(True, locked)
                        logging.error('process_unstaking: bad-txns-inputs-spent ({}), unlocked'.format(e.code))
                        return
                    raise
                sm.send_message('{} SOVE was unstacked\ntxid: `{}`'.format(u.amount, txid))
                sm.staking_pool_amount -= u.amount
                sm.save(update_fields=('staking_pool_amount',))
                u.fulfilled = True
                u.save()
                spc.api.lockunspent(True, locked)
        except:
            traceback.print_exc()
