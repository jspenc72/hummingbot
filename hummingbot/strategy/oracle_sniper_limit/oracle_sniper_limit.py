#!/usr/bin/env python
from decimal import Decimal
import os
import string
import sys
import json
import logging
import asyncio
import time
import base64

from terra_sdk.client.lcd import LCDClient
from terra_sdk.key.mnemonic import MnemonicKey
from terra_sdk.core.market import MsgSwap
from terra_sdk.client.lcd.api.oracle import OracleAPI
from terra_sdk.client.lcd.api.staking import StakingAPI
from terra_sdk.client.lcd.api.wasm import WasmAPI
from terra_sdk.core.wasm import MsgStoreCode, MsgInstantiateContract, MsgExecuteContract
from terra_sdk.core.auth.data.tx import StdFee
from terra_sdk.core import Coin, Coins

from hummingbot.strategy.limit_order.limit_order_utils import LimitOrderUtils
from hummingbot.strategy.limit_order.limit_order_config_map import limit_order_config_map as c_map
from hummingbot.core.event.events import OrderType
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.strategy_py_base import StrategyPyBase

# https://docs.anchorprotocol.com/smart-contracts/deployed-contracts

hws_logger = None

class OracleSniperLimit(StrategyPyBase):
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global hws_logger
        if hws_logger is None:
            hws_logger = logging.getLogger(__name__)
        return hws_logger

    def __init__(self):

        super().__init__()    
    
    def tick(self, timestamp: float):
        print(timestamp)

    async def format_status(self) -> str:
        """
        Returns a status string formatted to display nicely on terminal. The strings composes of 4 parts: markets,
        assets, profitability and warnings(if any).
        """
        status = ''
        rows = ['ROW1', "ROW2"]
        sections = []

        return "\n".join(rows)