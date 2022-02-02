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

# import pandas
# import numpy as np  # noqa
# import pandas as pd  # noqa
# from pandas import DataFrame

from terra_sdk.client.lcd import LCDClient
from terra_sdk.key.mnemonic import MnemonicKey
from terra_sdk.core.market import MsgSwap
from terra_sdk.client.lcd.api.oracle import OracleAPI
from terra_sdk.client.lcd.api.staking import StakingAPI
from terra_sdk.client.lcd.api.wasm import WasmAPI
from terra_sdk.core.wasm import MsgStoreCode, MsgInstantiateContract, MsgExecuteContract
from terra_sdk.core.auth.data.tx import StdFee
from terra_sdk.core import Coin, Coins
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.client.performance import PerformanceMetrics
from hummingbot.strategy.limit_order.limit_order_utils import LimitOrderUtils
from hummingbot.strategy.oracle_sniper_limit.oracle_sniper_limit_config_map import oracle_sniper_limit_config_map as c_map
from hummingbot.core.event.events import OrderType
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.strategy_py_base import StrategyPyBase
from hummingbot.strategy.oracle_sniper_limit.terra_service import TerraService

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
        self.ts = TerraService.instance()
        super().__init__()   
    
    def init_params(self, market_info_1, terra, offer_target,ask_target,token_target,token_pair):

        self.offer_target = offer_target
        self.ask_target = ask_target
        self.token_target = token_target
        self.token_pair = token_pair        
        self.terra = terra

        self._connector_ready = False
        self._tick_count = 0
        self._orders_completed_count = 0
        self._orders_attempted_count = 0
        self._market_info_1 = market_info_1
        self._all_markets_ready = False
        self._main_task = None
        self._order_quote_amount = 1
        self.utils = LimitOrderUtils(self.terra)

    def tick(self, timestamp: float):
        self._tick_count = self._tick_count+1
        self.logger().info("tick: "+str(self._tick_count)+" eval: "+ self.ask_target +" > "+ self.offer_target + " tc: "+ self.token_target)
        print(str(self._market_info_1.market.ready))
        if self.ready_for_new_arb_trades():
            if self._main_task is None or self._main_task.done():
                self._main_task = safe_ensure_future(self.main())    

    def ready_for_new_arb_trades(self) -> bool:
        """
        Returns True if there is no outstanding unfilled order.
        """
        return True

    def evaluate_token_pair_offset(self):
        self.pricing = self.utils.get_pair_pricing(self.token_target)    
        # Handle correct target pair
        market = c_map.get("TARGET_PAIR").value
        base, quote = market.split("-")
        target = ''
        if base == c_map.get("BASE_TX_CURRENCY").value:
            target = quote
        if quote == c_map.get("BASE_TX_CURRENCY").value:
            target = base       

        if c_map.get("ORDER_TYPE").value == "BUY":                              
            offset, price, trade, token = self.utils.get_token_buy_limit_order_offset(self.pricing, c_map.get("BASE_LIMIT_PRICE").value, target)
            self.current_offset = offset*10**-6
            self.current_price = price*10**-6
            self.current_trade = trade
            self.current_token = token
            self.logger().info(token)
            self.logger().info("Buy: offset, price, trade: "+str(offset*10**-6)+" "+str(price*10**-6)+" "+str(trade))
        else:
            offset, price, trade, token = self.utils.get_token_sell_limit_order_offset(self.pricing, c_map.get("BASE_LIMIT_PRICE").value, target)
            self.current_offset = offset*10**-6
            self.current_price = price*10**-6
            self.current_trade = trade
            self.current_token = token            
            self.logger().info(token)
            self.logger().info("Buy: offset, price, trade: "+str(offset)+" "+str(price)+" "+str(trade))
            self.logger().info("Sell: offset, price, trade: "+str(offset*10**-6)+" "+str(price*10**-6)+" "+str(trade))
        return offset, trade

    def evaluate_coin_pair_offset(self, tx_size):
        int_coin = Coin(self.offer_target, tx_size)
        rate = self.terra.market.swap_rate(int_coin, self.ask_target)
        self.logger().info("Limit Order: Simulating Swap before trade")
        self.logger().info("swap: "+str(tx_size) + self.offer_target +" > "+ self.ask_target)
        self.logger().info("current rate: ")
        self.logger().info(rate)

        if self.ORDER_TYPE == "BUY":
            offset, rate, trade = self.utils.get_coin_buy_limit_order_offset(rate, c_map.get("BASE_LIMIT_PRICE").value)
            self.logger().info("Buy: offset, rate, trade: "+str(offset)+" "+str(rate)+" "+str(trade))
            self.logger().info("Buy: offset, rate, trade: "+str(offset*10**-6)+" "+str(rate*10**-6)+" "+str(trade))

        else:
            offset, rate, trade = self.utils.get_coin_sell_limit_order_offset(rate, c_map.get("BASE_LIMIT_PRICE").value)
            self.logger().info("Sell: offset, rate, trade: "+str(offset)+" "+str(rate)+" "+str(trade))
            self.logger().info("Sell: offset, rate, trade: "+str(offset*10**-6)+" "+str(rate*10**-6)+" "+str(trade))
        
        if trade == False:
            self.logger().info("Limit Offset: ", offset)
        
        return offset, trade  

    async def main(self):
        """
        Clock tick entry point, is run every second (on normal tick setting).
        :param timestamp: current tick timestamp
        """
        # if self._market_info_1.market.ready:
        #     self.logger().warning(f"{self._market_info_1.market.name} is ready. Trading started")
        # else:
        #     self.logger().warning(f"{self._market_info_1.market.name} is not ready. Please wait...")
        #     return

        # A. Get Terraswap Wallet Balance
        # SECRET_TERRA_MNEMONIC = os.getenv('SECRET_TERRA_MNEMONIC')
        # if os.getenv("SECRET_TERRA_MNEMONIC") is not None:
        #     self.mk = MnemonicKey(mnemonic=SECRET_TERRA_MNEMONIC)
        #     self.wallet = self.terra.wallet(self.mk)
        #     self.balance = self.terra.bank.balance(self.mk.acc_address)
        #     self.last_trade_balance = self.terra.bank.balance(self.mk.acc_address)
        #     print("Terra Wallet Balance: ", self.balance)
        # else:
        #     self.logger().info("Something Went Wrong. Shutting Hummingbot down now...")
        #     time.sleep(3)
        #     sys.exit("Something Went Wrong!")

        # 1. Get Oracle Price
        for market_info in [self._market_info_1]:
            market, trading_pair, base_asset, quote_asset = market_info
            buy_price = await market.get_quote_price(trading_pair, True, self._order_quote_amount)
            sell_price = await market.get_quote_price(trading_pair, False, self._order_quote_amount)
            # check for unavailable price data
            buy_price = PerformanceMetrics.smart_round(Decimal(str(buy_price)), 8) if buy_price is not None else '-'
            sell_price = PerformanceMetrics.smart_round(Decimal(str(sell_price)), 8) if sell_price is not None else '-'
            mid_price = PerformanceMetrics.smart_round(((buy_price + sell_price) / 2), 8) if '-' not in [buy_price, sell_price] else '-'
            print("Exchange", "Market", "Sell Price", "Buy Price", "Mid Price")
            print(market.display_name, trading_pair, sell_price, buy_price, mid_price)

        # 2. Get Terraswap Price
        # balance = self.terra.bank.balance(self.mk.acc_address)
        # tx_size = self.utils.get_base_tx_size_from_balance(balance, self.utils.coin_to_denom(c_map.get("BASE_TX_CURRENCY").value), c_map.get("DEFAULT_BASE_TX_SIZE_PERCENTAGE_OF_BAL").value)

        # if tx_size == 0:
        #     self.logger().warning(f"computed transaction size is 0, check wallet balance: ")
        #     self.logger().warning(tx_size)
        #     return 


        # if self.token_target == '':
        #     self.is_coin_pair = True
        #     # Evaluate Trade
        #     offset, trade = self.evaluate_coin_pair_offset(tx_size)
        #     if trade == False:
        #         self.logger().info("Current Limit Offset: ", offset)
        #         return

        # elif self.token_target != '':    
        #     self.is_token_pair = True
        #     offset, trade = self.evaluate_token_pair_offset()
        #     if trade == False:
        #         self.logger().info("Current Limit Offset: ", offset)
        #         return


        # 3. Update Oracle Moving Average Price
        # 4. Compare Terraswap Price with Oracle Moving Average Price
        # 4.1. If (Terraswap Price) < (1-PERCENT)*(Oracle Moving Average Price) BUY
        # 4.2. If (Terraswap Price) > (1+PERCENT)*(Oracle Moving Average Price) SELL


    async def format_status(self) -> str:
        """
        Returns a status string formatted to display nicely on terminal. The strings composes of 4 parts: markets,
        assets, profitability and warnings(if any).
        """
        status = ''
        rows = ['ROW1', "ROW2"]
        sections = []

        configcols = [["MAX_NUM_TRADE_ATTEMPTS: ", c_map.get("MAX_NUM_TRADE_ATTEMPTS").value],["MINIMUM_WALLET_UST_BALANCE: ", c_map.get("MINIMUM_WALLET_UST_BALANCE").value],
                            ["BASE_TX_CURRENCY: ", c_map.get("BASE_TX_CURRENCY").value],
                            ["DEFAULT_BASE_TX_SIZE_PERCENTAGE_OF_BAL: ", c_map.get("DEFAULT_BASE_TX_SIZE_PERCENTAGE_OF_BAL").value],
                            ["DEFAULT_MAX_SPREAD: ", c_map.get("DEFAULT_MAX_SPREAD").value]]
        
        for value in configcols: 
            row = " ".join(value)
            rows.append(row)


        return "\n".join(rows)

class OracleSniperLimitPosition():

    # Limit Related Vars
    upper_limit_price = 0.0
    lower_limit_price = 0.0
    # MA Related Vars
    MA_NUM_TICKS=60
    moving_average = 0.0
    averaged_ticks = []
    #Related Vars
    oracle_price = 0.0


    def __init__(self, 
                    upper_limit_price, 
                    lower_limit_price,
                    MA_NUM_TICKS):
        self.upper_limit_price = upper_limit_price
        self.lower_limit_price = lower_limit_price
        self.MA_NUM_TICKS = MA_NUM_TICKS
        super().__init__()

    def create_buy_contract(self, amount, currency):
        print("create_buy_contract")

    def create_sell_contract(self, amount, currency):
        print("create_sell_contract")

    def execute_contract(self, contract):
        print('execute_contract')
