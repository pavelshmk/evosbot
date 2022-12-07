from decimal import Decimal
from time import sleep

import requests
from celery_once import QueueOnce
from dynamic_preferences.registries import global_preferences_registry

from app.models import Masternode, UserNode
from evosbot.celery import app
from evosbot.utils import masternode_client, get_masternode_price, usernode_client, client

global_preferences = global_preferences_registry.manager()
global_preferences['internal__usernode_lock'] = False


@app.task(name='app.tasks.usernode_create', base=QueueOnce, once={'graceful': True})
def usernode_create():
    if global_preferences['internal__usernode_lock']:
        return

    global_preferences['internal__usernode_lock'] = True
    try:
        masternode_price = get_masternode_price()

        masternodes = UserNode.objects.filter(pending=True)
        if not masternodes.count():
            return
        masternodes = list(masternodes)

        outputs = {}
        for mn in masternodes:
            mn.wallet_address = usernode_client.api.getnewaddress()
            outputs[mn.wallet_address] = masternode_price
        txid = client.send_funds_multiple(outputs)
        for mn in masternodes:
            mn.output_txid = txid

        sleep(5)
        while True:
            mn_outputs = list(filter(lambda o: o.get('txhash') == txid, usernode_client.api.masternode('outputs')))
            if mn_outputs:
                break
        indexes = [o['outputidx'] for o in mn_outputs]
        for mn, idx in zip(masternodes, indexes):
            mn.output_idx = idx
            mn.pending = False
            mn.save()

        r = requests.post(global_preferences['general__usernode_service_uri'] + '/config', json={
            'content': UserNode.generate_config(),
        })
        if r.text == 'OK':
            current_block = usernode_client.api.getblockcount()
            r = requests.post(global_preferences['general__usernode_service_uri'] + '/reload')
            if r.text == 'OK':
                while True:
                    try:
                        usernode_client.api.getblockcount()
                        break
                    except:
                        sleep(5)
                while usernode_client.api.getblockcount() - current_block < 15:
                    print('Diff is', usernode_client.api.getblockcount() - current_block, 'blocks')
                    sleep(60)
                for mn in masternodes:
                    result = usernode_client.api.startmasternode('alias', '0', mn.alias)
                    print(result)
    finally:
        global_preferences['internal__usernode_lock'] = False
