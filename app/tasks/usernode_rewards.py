import logging
import math
from decimal import Decimal
from time import sleep

import requests
from celery_once import QueueOnce
from dynamic_preferences.registries import global_preferences_registry

from app.models import Masternode, UserNode, ServerMember
from evosbot.celery import app
from evosbot.utils import masternode_client, get_masternode_price, usernode_client, client, fd

global_preferences = global_preferences_registry.manager()


@app.task(name='app.tasks.usernode_rewards', base=QueueOnce, once={'graceful': True})
def usernode_rewards():
    inputs = []
    outputs = {}
    for un in UserNode.objects.filter(pending=False):  # type: UserNode
        un_inputs = usernode_client.api.listunspent(1, 2147483647, [un.wallet_address])
        un_inputs = list(filter(lambda un: un.get('vout', 0) > 1, un_inputs))
        s = sum(i['amount'] for i in un_inputs)
        if s > 0:
            inputs.extend(un_inputs)
            outputs[un.member.wallet_address] = s
            un.member.send_message('You have received masternode reward of {}'.format(fd(s)))

    if not len(outputs):
        return

    logging.warning(inputs)
    logging.warning(outputs)
    fee = usernode_client.estimate_fee(1)
    estimate_tx = usernode_client.api.createrawtransaction(inputs, outputs)
    estimate_tx = usernode_client.api.signrawtransaction(estimate_tx)
    fee *= math.ceil(len(bytes.fromhex(estimate_tx['hex'])) / 1024 + 1)
    fee_each = fee / len(outputs)
    for addr in outputs:
        outputs[addr] -= fee_each

    tx = usernode_client.api.createrawtransaction(inputs, outputs)
    tx = usernode_client.api.signrawtransaction(tx)
    txid = usernode_client.api.sendrawtransaction(tx['hex'])
    logging.info('Reward was sent successfully: {}'.format(txid))
