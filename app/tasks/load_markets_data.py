from decimal import Decimal

import requests
from dynamic_preferences.registries import global_preferences_registry

from evosbot.celery import app

global_preferences = global_preferences_registry.manager()


@app.task(name='app.tasks.load_markets_data')
def load_markets_data():
    crex_info = requests.get('https://api.crex24.com/v2/public/tickers', params={
        'instrument': 'SOVE-BTC,BTC-USD'
    }).json()
    crex_info = {i['instrument']: i for i in crex_info}
    btc_price = crex_info['BTC-USD']['last']
    global_preferences['internal__crex24_volume'] = Decimal(crex_info['SOVE-BTC']['volumeInBtc'])
    global_preferences['internal__crex24_price'] = Decimal(crex_info['SOVE-BTC']['last'] * btc_price)

    graviex_btcusd_data = requests.get('https://graviex.net:443/api/v3/tickers/btcusd.json').json()
    graviex_data = requests.get('https://graviex.net:443/api/v3/tickers/sovebtc.json').json()
    btc_price = Decimal(graviex_btcusd_data['last'])
    global_preferences['internal__graviex_volume'] = Decimal(graviex_data['volume2'])
    global_preferences['internal__graviex_price'] = Decimal(graviex_data['last']) * btc_price

#    cb_btcusd_data = requests.get('https://api.crypto-bridge.org/v2/market/pubticker/BTC_USDT').json()
#    cb_data = requests.get('https://api.crypto-bridge.org/v2/market/pubticker/SOVE_BTC').json()
#    btc_price = Decimal(cb_btcusd_data['last_price'])
#    global_preferences['internal__cryptobridge_volume'] = Decimal(cb_data['volume'])
#    global_preferences['internal__cryptobridge_price'] = Decimal(cb_data['last_price']) * btc_price
