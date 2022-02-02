#!/usr/bin/env python
from lib2to3.pgen2 import token
from terra_sdk.client.lcd import LCDClient
import requests
import json
import os 
import time
import sys
from terra_sdk.key.mnemonic import MnemonicKey
from hummingbot.strategy.limit_order import LimitOrderUtils
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.oracle_sniper_limit import OracleSniperLimit
from hummingbot.strategy.oracle_sniper_limit.oracle_sniper_limit_config_map import oracle_sniper_limit_config_map as c_map
from hummingbot.strategy.oracle_sniper_limit.terra_service import TerraService

def start(self):
    ts = TerraService.instance()
    ts.test()
    try:
        self.terra = LCDClient(chain_id="columbus-5", url="https://lcd.terra.dev")
        self.utils = LimitOrderUtils(self.terra)
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)

    connector_1 = c_map.get("connector_2").value.lower()
    market_1 = c_map.get("ORACLE_PAIR").value
    target_pair = c_map.get("TARGET_PAIR").value
    base_1, quote_1 = market_1.split("-")
    target_base, target_quote = target_pair.split("-")

    self._initialize_markets([(connector_1, [market_1])])
    market_info_1 = MarketTradingPairTuple(self.markets[connector_1], market_1, base_1, quote_1)
    self.market_trading_pair_tuples = [market_info_1]    

    cw20_pairs = requests.get('https://api.terraswap.io/dashboard/pairs').json()
    asset_info_pairs = requests.get('https://api.terraswap.io/pairs').json()

    print(target_base + " - " + target_quote)

    # Find offer target denom
    pair = []
    token_target = ''
    offer_target = ''
    ask_target = ''
    print("pair "+target_pair+". "+ target_base +"-"+ target_quote +"  searching for matching Terra ERC20 tokens by pairAlias")
    # go through pairs
    pair = self.utils.find_token_pair_contract_from_pairs(cw20_pairs, target_pair)
    print(pair)
    if 'pairAddress' in pair:
        print("token pair lookup successful")
        token_target = pair['pairAddress']
        pair_asset_info = self.utils.find_asset_info_from_pair(pair['pairAddress'], asset_info_pairs['pairs'])
        print("asset_info lookup successful")
        print(pair_asset_info)
        offer_target = pair['token0']
        ask_target = pair['token1']
        # TOKEN-PAIR
        self.strategy = OracleSniperLimit()
        self.strategy.init_params(market_info_1=market_info_1, 
                                    terra=self.terra,
                                    offer_target=offer_target,
                                    ask_target=ask_target,
                                    token_target=token_target,
                                    token_pair=pair)        
    else: 
        # SOMETHING-Luna
        print("market is "+target_pair+" token to coin, only option is token to Luna!")
        print("unknown trade type, cannot find matching pair")
        offer_target = self.utils.coin_to_denom(target_base)
        ask_target = self.utils.coin_to_denom(target_quote)
        # Find ask target denom
        if offer_target != '' and ask_target != '':
            print("found trading pair: ", offer_target, ask_target)
            try:

                
                self.strategy = OracleSniperLimit()
                self.strategy.init_params(market_info_1=market_info_1, 
                                            terra=self.terra,
                                            offer_target=offer_target,
                                            ask_target=ask_target,
                                            token_target=token_target,
                                            token_pair=pair)
            except Exception as e:
                self._notify(str(e))
                self.logger().error("Unknown error during initialization.", exc_info=True)

        else:
            # COIN-COIN
            print('unable to find trading pair')
    print("final trading pair: ", offer_target +" > " + ask_target)






