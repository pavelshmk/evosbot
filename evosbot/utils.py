import io
import json
import logging
import math
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

import requests
from slickrpc import Proxy
from django.template.loader import render_to_string
from dynamic_preferences.registries import global_preferences_registry
from weasyprint import HTML

from slickrpc.exc import RpcException

global_preferences = global_preferences_registry.manager()
tx_logger = logging.getLogger('tx')
rank_logger = logging.getLogger('rank')


class Wallet(Enum):
    main = 0
    staking = 1
    staking_pool = 2
    masternode = 3
    bitcoin = 4
    usernode = 5


class RPCClient:
    RPCException = RpcException

    def __init__(self, wallet_type: Wallet):
        self.wallet_type = wallet_type

    @property
    def rpc_url(self):
        if self.wallet_type == Wallet.main:
            return global_preferences['general__main_wallet_uri']
        elif self.wallet_type == Wallet.staking:
            return global_preferences['general__staking_wallet_uri']
        elif self.wallet_type == Wallet.staking_pool:
            return global_preferences['general__staking_pool_wallet_uri']
        elif self.wallet_type == Wallet.masternode:
            return global_preferences['general__masternode_wallet_uri']
        elif self.wallet_type == Wallet.bitcoin:
            return global_preferences['general__bitcoin_wallet_uri']
        elif self.wallet_type == Wallet.usernode:
            return global_preferences['general__usernode_wallet_uri']

    @property
    def api(self):
        return Proxy(self.rpc_url)

    def get_balance(self, account='*', minconf=None):
        if minconf is None:
            minconf = 2
        return self.api.getbalance(account, minconf)

    def create_address(self, account=''):
        return self.api.getnewaddress(account)

    def validate_address(self, address):
        return self.api.validateaddress(address)['isvalid']

    def received_by_address(self, confirmations=None):
        if confirmations is None:
            confirmations = global_preferences['general__confirmations_needed']
        return self.api.listreceivedbyaddress(confirmations)

    def send_funds_multiple(self, outputs: dict, inputs: list = None, change_addr: str = None):
        logging.warning('calculating inputs')
        total_amount = sum(outputs.values())
        inputs_sum = 0
        if inputs is None:
            inputs = []
            logging.warning('getting unspents')
            unspents = self.api.listunspent(global_preferences['general__confirmations_needed'])
            logging.warning('sorting unspents')
            unspents = list(sorted(filter(lambda u: u.get('spendable'), unspents), key=lambda u: u['amount']))
            for u in unspents:
                if inputs_sum >= total_amount:
                    break
                inputs_sum += u['amount']
                inputs.append({'txid': u['txid'], 'vout': u['vout'], 'amount': u['amount']})
        else:
            inputs_sum = sum(u['amount'] for u in inputs)

        logging.warning('getting change address')
        fee = self.estimate_fee(1)
        if change_addr is None:
            change_addr = self.api.getnewaddress()
        outputs = outputs.copy()
        outputs[change_addr] = 0
        if inputs_sum > total_amount:
            outputs[change_addr] = inputs_sum - total_amount
        elif inputs_sum < total_amount:
            raise RuntimeError('Insufficient balance')

        logging.warning(inputs)
        logging.warning(outputs)

        estimate_tx = self.api.createrawtransaction(inputs, outputs)
        estimate_tx = self.api.signrawtransaction(estimate_tx)
        fee *= math.ceil(len(bytes.fromhex(estimate_tx['hex'])) / 1024 + 1)

        outputs[change_addr] -= fee
        if outputs[change_addr] < 0:
            raise RuntimeError('Insufficient balance')
        elif outputs[change_addr] == 0:
            del outputs[change_addr]
        tx = self.api.createrawtransaction(inputs, outputs)
        tx = self.api.signrawtransaction(tx)
        txid = self.api.sendrawtransaction(tx['hex'])
        return txid

    def send_funds(self, to, amount):
        return self.send_funds_multiple({to: amount})

    def estimate_fee(self, conf):
        fee = self.api.estimatefee(conf)
        if fee < 0:
            return Decimal('.0001')
        if fee > 0.1:
            return Decimal('.0009')
        return fee

    def minimal_spend(self):
        return global_preferences['general__transaction_commission'] * 2


client = RPCClient(Wallet.main)
staking_client = RPCClient(Wallet.staking)
staking_pool_client = RPCClient(Wallet.staking_pool)
masternode_client = RPCClient(Wallet.masternode)
bitcoin_client = RPCClient(Wallet.bitcoin)
usernode_client = RPCClient(Wallet.usernode)


def staking_pool_address():
    if not global_preferences['internal__staking_pool_address']:
        global_preferences['internal__staking_pool_address'] = staking_pool_client.api.getaccountaddress('pool')
    return global_preferences['internal__staking_pool_address']


def masternode_address():
    if not global_preferences['internal__masternode_address']:
        global_preferences['internal__masternode_address'] = masternode_client.api.getaccountaddress('masternode')
    return global_preferences['internal__masternode_address']


def get_api_session():
    api_session = requests.Session()
    api_session.headers = {'Authorization': 'Bot {}'.format(global_preferences['general__bot_token'])}
    return api_session


def send_discord_message(channel, content, file=None):
    return get_api_session().post('https://discordapp.com/api/v6/channels/{}/messages'.format(channel), {
        'payload_json': json.dumps({'content': content})
    }, files={'file': file})


def get_member(guild_id, user_id):
    return get_api_session().get(
        'https://discordapp.com/api/v6/guilds/{}/members/{}'.format(guild_id, user_id),
        timeout=5
    ).json()


def get_members(guild_id, after=0):
    return get_api_session().get('https://discordapp.com/api/v6/guilds/{}/members'.format(guild_id),
                                 params={'limit': 1000, 'after': after}).json()


def set_roles(guild_id, user_id, roles):
    return get_api_session().patch(
        'https://discordapp.com/api/v6/guilds/{}/members/{}'.format(guild_id, user_id),
        json={
            'roles': roles,
        },
        timeout=5
    )


def get_masternode_price():
    locked = masternode_client.api.masternode('outputs')
    if not locked:
        raise RuntimeError('Could not get masternode price')
    tx_hex = masternode_client.api.getrawtransaction(locked[0]['txhash'])
    decoded = masternode_client.api.decoderawtransaction(tx_hex)
    return decoded['vout'][locked[0]['outputidx']]['value']


def get_rewards():
    last_block_hash = client.api.getbestblockhash()
    block = client.api.getblock(last_block_hash)
    tx_hex = client.api.getrawtransaction(block['tx'][1])
    tx = client.api.decoderawtransaction(tx_hex)

    inputs = 0
    for txin in tx['vin']:
        input_tx = client.api.decoderawtransaction(client.api.getrawtransaction(txin['txid']))
        inputs += input_tx['vout'][txin['vout']]['value']

    pos_reward = sum(vout['value'] for vout in tx['vout'][1:-1]) - inputs
    mn_reward = tx['vout'][-1]['value']

    return pos_reward, mn_reward


def send_stats(channel=None):
    from app.models import OrderLog, Masternode, UserNode

    lo = OrderLog.objects.last()
    last_deal = lo.btc_price if lo else 0
    block_count = client.api.getblockcount()
    total_masternodes = max(m['rank'] for m in client.api.masternode('list'))
    shared_masternodes = Masternode.objects.filter(active=True).count()
    user_masternodes = UserNode.objects.filter(pending=False, active=True).count()
    masternode_price = get_masternode_price()
    last_day_blocks = 0
    last_block_hash = client.api.getbestblockhash()
    while True:
        block = client.api.getblock(last_block_hash)
        if datetime.fromtimestamp(block['time']) < datetime.now() - timedelta(1):
            break
        last_day_blocks += 1
        last_block_hash = block['previousblockhash']
    pos_reward, mn_reward = get_rewards()
    amroi = last_day_blocks * mn_reward * 365 / masternode_price / total_masternodes * 100
    pool_balance = masternode_client.get_balance()
    stack_median = global_preferences['internal__stack_median']

    html = render_to_string('stats.html', {
        'amroi': amroi,
        'block_count': block_count,
        'pos_reward': pos_reward,
        'mn_reward': mn_reward,
        'total_masternodes': total_masternodes,
        'shared_masternodes': shared_masternodes,
        'user_masternodes': user_masternodes,
        'pool_balance': pool_balance,
        'stack_median': stack_median,
        'last_deal': last_deal,
    })
    png = io.BytesIO(HTML(string=html).write_png())
    png.name = 'stats.png'
    r = send_discord_message(channel or global_preferences['general__reward_report_channel_id'], '', png)


def fd(val):
    return '{:.8f}'.format(val).rstrip('0').rstrip('.')
