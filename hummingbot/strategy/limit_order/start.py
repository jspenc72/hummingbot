#!/usr/bin/env python
from terra_sdk.client.lcd import LCDClient
import requests
import json
import os 

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.limit_order import LimitOrder
from hummingbot.strategy.limit_order.limit_order_config_map import limit_order_config_map as c_map

def start(self):
    try:
        connector = c_map.get("connector").value.lower()
        market = c_map.get("market").value

        self._initialize_markets([(connector, [market])])
        base, quote = market.split("-")
        market_info = MarketTradingPairTuple(self.markets[connector], market, base, quote)
        self.market_trading_pair_tuples = [market_info]
        terra = LCDClient(chain_id="columbus-4", url="https://lcd.terra.dev")
        # Opening JSON file
        cwd = os.getcwd() 
        cw20_path = cwd+'/hummingbot/strategy/limit_order/cw20.json'
        ibc_path = cwd+'/hummingbot/strategy/limit_order/ibc.json'
        fcw20 = open(cw20_path)
        fibc = open(ibc_path)
        # returns JSON object as
        # a dictionary
        cw20_data = json.load(fcw20)
        ibc_data = json.load(fibc)
        
        # cw20tokens = requests.get('https://assets.terra.money/cw20/tokens.json').json()
        # ibctokens = requests.get('https://assets.terra.money/ibc/tokens.json').json()
        # cw20pairs = requests.get('https://assets.terra.money/cw20/pairs.dex.json').json()
        # terracontracts = requests.get('https://assets.terra.money/contracts.json').json()
        # ibctokens = requests.get('https://assets.terra.money/chains.json').json()

        self.strategy = LimitOrder(market_info, 
                                    terra_client=terra, 
                                    terra_ibc_tokens=ibc_data, 
                                    terra_cw20_tokens=cw20_data)

    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)
