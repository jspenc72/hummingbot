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

def start(self):
    try:
        self.terra = LCDClient(chain_id="columbus-5", url="https://lcd.terra.dev")
        self.strategy = OracleSniperLimit()
    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)

