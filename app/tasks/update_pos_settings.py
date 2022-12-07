import statistics
from decimal import Decimal

from celery_once import QueueOnce
from dynamic_preferences.registries import global_preferences_registry

from evosbot.celery import app
from evosbot.utils import staking_pool_client, masternode_client


global_preferences = global_preferences_registry.manager()


@app.task(name='app.tasks.update_pos_settings', base=QueueOnce, once={'graceful': True})
def update_pos_settings():
    last_block_num = staking_pool_client.api.getblockcount()
    vals = []
    for bn in range(last_block_num, last_block_num - 120, -1):
        bh = staking_pool_client.api.getblockhash(bn)
        if bh.startswith('0000'):
            continue
        b = staking_pool_client.api.getblock(bh)
        if len(b['tx']) < 2:
            continue
        rtx = staking_pool_client.api.getrawtransaction(b['tx'][1])
        tx = staking_pool_client.api.decoderawtransaction(rtx)
        if len(tx['vout']) < 2:
            continue
        vals.append(tx['vout'][1]['value'])
    value = global_preferences['internal__stack_median'] = statistics.median(vals)
    staking_pool_client.api.autocombinerewards(True, int(value))
    staking_pool_client.api.setstakesplitthreshold(int(value * Decimal('1.2')))
    masternode_client.api.autocombinerewards(True, int(value))
    masternode_client.api.setstakesplitthreshold(int(value * Decimal('1.2')))
