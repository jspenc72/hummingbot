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
    positions = []
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global hws_logger
        if hws_logger is None:
            hws_logger = logging.getLogger(__name__)
        return hws_logger

    def __init__(self):
        self.terra_service = TerraService.instance()
        
        for x in range(1):
            p = OracleSniperLimitPosition()
            self.positions.append(p)


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
        self.logger().info("----------------TICKSTART----------------")
        self.logger().info("tick: "+str(self._tick_count)+" eval: "+ self.ask_target +" > "+ self.offer_target + " tc: "+ self.token_target[0:15])
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
        balance  = await self.terra_service.request_updated_wallet_balance()
        # 2. Get Terraswap Ask Target Price
        market = c_map.get("TARGET_PAIR").value
        base, quote = market.split("-")        
        self.ask_target_pricing = self.terra_service.get_token_pricing(self.token_target, base)
        self.pricing = self.terra_service.get_pair_pricing(self.token_target)
        
        if market == 'Luna-UST': 
            wallet_ask_asset_balance = balance.get(self.terra_service.coin_to_denom(base))
        else:
            wallet_ask_asset_balance = balance.get(self.terra_service.coin_to_denom(quote))

        print(self.ask_target_pricing)
        # 1. Get Oracle Price
        for market_info in [self._market_info_1]:
            market, trading_pair, base_asset, quote_asset = market_info
            print("did request updated oracle pricing: "+trading_pair)
            buy_price = await market.get_quote_price(trading_pair, True, self._order_quote_amount)
            sell_price = await market.get_quote_price(trading_pair, False, self._order_quote_amount)
            # check for unavailable price data
            buy_price = PerformanceMetrics.smart_round(Decimal(str(buy_price)), 8) if buy_price is not None else '-'
            sell_price = PerformanceMetrics.smart_round(Decimal(str(sell_price)), 8) if sell_price is not None else '-'
            mid_price = PerformanceMetrics.smart_round(((buy_price + sell_price) / 2), 8) if '-' not in [buy_price, sell_price] else '-'
            if buy_price == '-':
                print('oracle price data unavailable')
                return
            ask_price = Decimal(self.ask_target_pricing['price'])
            print("Exchange", "Market", "Sell Price", "Buy Price", "Mid Price", self.ask_target_pricing['symbol']+" ASK PRICE")
            print(market.display_name, trading_pair, sell_price, buy_price, mid_price, ask_price)
            # round ask price
            ask_price = PerformanceMetrics.smart_round(ask_price, 8)
        for position in self.positions:
            position.eval_pricing(ask_price, buy_price, sell_price, mid_price, balance)
            position.update_buy_params(pool=self.token_target, pricing=self.pricing)

        self.logger().info("----------------TICKEND----------------")

        # 3. Update Oracle Moving Average Price
        # Check Buy Sell Criteria

        # 4. Compare Terraswap Price with Oracle Moving Average Price
        # 4.1. If (Terraswap Price) < (1-PERCENT)*(Oracle Moving Average Price) BUY
        # 4.2. If (Terraswap Price) > (1+PERCENT)*(Oracle Moving Average Price) SELL

    async def format_status(self) -> str:
        """
        Returns a status string formatted to display nicely on terminal. The strings composes of 4 parts: markets,
        assets, profitability and warnings(if any).
        """

        status = ''
        rows = []
        sections = []

        configcols = [["strategy: ", c_map.get("strategy").value],
                        ["connector_1: ", c_map.get("connector_1").value],
                        ["connector_2: ", c_map.get("connector_2").value],
                        ["MAX_NUM_TRADE_ATTEMPTS: ", c_map.get("MAX_NUM_TRADE_ATTEMPTS").value],
                        ["MINIMUM_WALLET_UST_BALANCE: ", c_map.get("MINIMUM_WALLET_UST_BALANCE").value],
                        ["ORACLE_PAIR: ", c_map.get("ORACLE_PAIR").value],
                        ["TARGET_PAIR: ", c_map.get("TARGET_PAIR").value],
                        ["OFFER_ASSET: ", c_map.get("OFFER_ASSET").value],
                        ["ORDER_TYPE: ", c_map.get("ORDER_TYPE").value],
                        ["BASE_LIMIT_PRICE: ", c_map.get("BASE_LIMIT_PRICE").value],
                        ["BASE_TX_CURRENCY: ", c_map.get("BASE_TX_CURRENCY").value],
                        ["DEFAULT_BASE_TX_SIZE_PERCENTAGE_OF_BAL: ", c_map.get("DEFAULT_BASE_TX_SIZE_PERCENTAGE_OF_BAL").value],
                        ["DEFAULT_MAX_SPREAD: ", c_map.get("DEFAULT_MAX_SPREAD").value],
                        ["PAPER_TRADE: ", c_map.get("PAPER_TRADE").value],
                        ["MOVING_AVERAGE_TICKS: ", c_map.get("MOVING_AVERAGE_TICKS").value],
                        ["MOVING_AVERAGE_WINDOW: ", c_map.get("MOVING_AVERAGE_WINDOW").value],
                        ["UPPER_LIMIT_PERCENT: ", c_map.get("UPPER_LIMIT_PERCENT").value],
                        ["LOWER_LIMIT_PERCENT: ", c_map.get("LOWER_LIMIT_PERCENT").value]]
        
        for value in configcols: 
            row = " ".join(value)
            rows.append(row)

        for position in self.positions:
            ln1, ln2, ln3 = position.output_status()
            rows.append(ln1)
            rows.append(ln2)
            rows.append(ln3)

        return "\n".join(rows)

class OracleSniperLimitPosition():

    current_position_amount = 0

    # Config Parameters
    target_pair = c_map.get("TARGET_PAIR").value
    oracle_pair = c_map.get("ORACLE_PAIR").value
    offer_asset = c_map.get("OFFER_ASSET").value
    max_num_trade_attempts = c_map.get("MAX_NUM_TRADE_ATTEMPTS").value
    minimum_wallet_ust_balance = int(c_map.get("MINIMUM_WALLET_UST_BALANCE").value)
    upper_limit_percentage_of_oracle_ma = PerformanceMetrics.smart_round(Decimal(c_map.get("UPPER_LIMIT_PERCENT").value), 4)
    lower_limit_percentage_of_oracle_ma = PerformanceMetrics.smart_round(Decimal(c_map.get("LOWER_LIMIT_PERCENT").value), 4)
    MA_NUM_TICKS=int(c_map.get("MOVING_AVERAGE_TICKS").value)
    MA_window_size=int(c_map.get("MOVING_AVERAGE_WINDOW").value)

    # Trading Vars
    trigger_buy_price = 0.0 
    trigger_sell_price = 0.0 
    oracle_sell_price = 0.0
    oracle_buy_price = 0.0
    oracle_mid_price = 0.0
    ask_pricing = 0.0
    target_token = ''
    # Trade Metrics
    orders_attempted_count = 0
    orders_completed_count = 0
    # Terra Wallet
    balance = Coin('uust', 1)
    pricing = None
    # Pricing Series
    oracle_mid_price_series = []
    oracle_mid_price_series_ma = []
    oracle_lower_price_series = []
    oracle_lower_price_series_ma = []
    oracle_upper_price_series = []
    oracle_upper_price_series_ma = []
    ask_price_series = []
    ask_price_series_ma = []
    # MA Related Vars
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global hws_logger
        if hws_logger is None:
            hws_logger = logging.getLogger(__name__)
        return hws_logger


    def __init__(self):
        self.terra_service = TerraService.instance()
        super().__init__()

    def create_buy_contract(self, amount, currency):
        print("create_buy_contract")

    def create_sell_contract(self, amount, currency):
        print("create_sell_contract")

    def execute_contract(self, contract):
        print('execute_contract')

    def calculate_position(self):
        self.calculate_moving_averages()
        self.calculate_offsets()
        safe_ensure_future(self.handle_offsets())

    def calculate_offsets(self):
        # x*(oracle_mid_price)=ask_pricing
        #   
        
        self.terra_ask_percent_of_oracle_mid = PerformanceMetrics.smart_round(Decimal(self.ask_pricing / self.oracle_mid_price ), 8)
        self.ask_pricing_difference_oracle_mid = PerformanceMetrics.smart_round(Decimal(self.ask_pricing - self.oracle_mid_price), 8)

        # 4.1. If (Terraswap Price) < (1-PERCENT)*(Oracle MID Moving Average Price) then BUY
        # 4.1. If (Terraswap Price) < (1-0.1)*(Oracle MID Moving Average Price) then BUY

        # 4.2. If (Terraswap Price) > (1+PERCENT)*(Oracle MID Moving Average Price) then SELL
        # 4.2. If (Terraswap Price) > (1+0.1)*(Oracle MID Moving Average Price) then SELL
    def joinStrings(spacer, *argv):
        res = ''
        for arg in argv:
            res = res + spacer + str(arg)
        return res

    def output_status(self):
        ln1 = ["Tick:", 'ask_pricing', 'trigger_*_price', 'oracle mid price', 'buy/sell', 'conf %', 'calc %']
        ln1 = " ".join(ln1)
        print(ln1)
        ln2 = ["Buy Criteria:", str(self.ask_pricing), str(self.trigger_buy_price), str(self.oracle_mid_price), str(self.ask_pricing < self.trigger_buy_price), str(self.lower_limit_percentage_of_oracle_ma), str(self.terra_ask_percent_of_oracle_mid)]
        ln2 = " ".join(ln2)
        print(ln2)
        ln3 = ["Sell Criteria:", str(self.ask_pricing), str(self.trigger_sell_price), str(self.oracle_mid_price), str(self.ask_pricing > self.trigger_sell_price), str(self.upper_limit_percentage_of_oracle_ma), str(self.terra_ask_percent_of_oracle_mid)]
        ln3 = " ".join(ln3)
        print(ln3)
        return ln1, ln2, ln3

    def output_should_buy_warning(self):
        joinedstro = " - ".join(["Buy Criteria Met:", 'ask_pricing', 'oracle mid', 'oracle sell', 'oracle buy', 'config %', 'calc %'])
        self.logger().info(joinedstro)
        joinedstr = " - ".join(["Terraswap Price:", str(self.ask_pricing) , str(self.oracle_mid_price) , str(self.oracle_sell_price),str(self.oracle_buy_price),str(self.lower_limit_percentage_of_oracle_ma),str(self.terra_ask_percent_of_oracle_mid)])
        self.logger().info(joinedstr)

    def output_should_sell_warning(self):
        joinedstro = " - ".join(["Sell Criteria Met:", 'ask_pricing', 'oracle mid', 'oracle sell', 'oracle buy', 'config %', 'calc %'])
        self.logger().info(joinedstro)
        joinedstr = " - ".join(["Terraswap Price:", str(self.ask_pricing), str(self.oracle_mid_price), str(self.oracle_sell_price), str(self.oracle_buy_price), str(self.upper_limit_percentage_of_oracle_ma),str(self.terra_ask_percent_of_oracle_mid)])
        self.logger().info(joinedstr)
        
    async def handle_offsets(self):
        self.trigger_buy_price = PerformanceMetrics.smart_round(Decimal(1-self.lower_limit_percentage_of_oracle_ma)*self.oracle_mid_price, 8)
        self.trigger_sell_price = PerformanceMetrics.smart_round(Decimal(1+self.upper_limit_percentage_of_oracle_ma)*self.oracle_mid_price, 8)
        self.output_status()        
        self.logger().info("Evaluating Buy..")
        if self.ask_pricing < self.trigger_buy_price:
            self.output_should_buy_warning()
            # Check criteria
            # 1. Check current position self.current_position_amount==0
            if not self.current_position_amount==0:
                self.logger().warn(u'\N{LATIN SMALL LETTER O WITH STROKE} Skipping Buy, Holding Position: '+self.current_position_amount)
                return
            self.logger().info(u'\N{check mark} Current Position is '+str(self.current_position_amount))
            # 2. # trades below Max Num Trades Threshold
            print(str(self.trade_eval_num_trades_below_threshold()))
            if not self.trade_eval_num_trades_below_threshold():
                self.logger().info(u'\N{LATIN SMALL LETTER O WITH STROKE} Trade Count Above Threshold')
                self.logger().warn(str(self.orders_attempted_count) +" / "+ str(self.orders_completed_count) +" / "+ str(self.max_num_trade_attempts))
                return 
            self.logger().info(u'\N{check mark} Trade Count Below Threshold')
            self.logger().warn(str(self.orders_attempted_count) +" / "+ str(self.orders_completed_count) +" / "+ str(self.max_num_trade_attempts))
            # 3. Check Wallet UST Balance Above Threshold
            if not self.trade_eval_ust_balance_above_threshold():
                return 
            self.logger().info(u'\N{check mark} UST Balance Above Threshold')
            # 4. Execute Buy Contract
            pool, amount, sellinfo, belief_price, max_spread = await self.trade_generate_buy_contract_values()
            self.logger().info('Contract vars')
            self.orders_attempted_count = self.orders_attempted_count+1
            contract_vars = " ".join([str(pool), str(amount), str(json.dumps(sellinfo)), str(belief_price), str(max_spread)])
            self.logger().info(contract_vars)
            if c_map.get("PAPER_TRADE").value == 'True':
                self.logger().info(u'\N{check mark} ------- PAPER TRADE BUY -------: '+ c_map.get("PAPER_TRADE").value)
                self.balance  = await self.terra_service.request_updated_wallet_balance()
                self.logger().info(self.balance)
                return
            else:
                result = self.terra_service.token_swap(pool, amount, sellinfo, belief_price, max_spread)
                self.logger().info("outputting transaction log..")
                self.logger().info(result.txhash)
                self.logger().warn(result.raw_log)
                self.logger().info("transaction complete..")
                self.orders_completed_count = self.orders_completed_count+1
                self.balance  = await self.terra_service.request_updated_wallet_balance()
                self.logger().info(self.balance)

        self.logger().info("Evaluating Sell..")
        if self.ask_pricing > self.trigger_sell_price:
            self.output_should_sell_warning()
            # Check criteria
            # 1. Check current position self.current_position_amount==0 
            if self.current_position_amount==0:
                self.logger().warn("No position to sell: "+str(self.current_position_amount))
                return            
            # 2. # trades below Max Num Trades Threshold
            if not self.trade_eval_num_trades_below_threshold():
                return 
            self.logger().info(u'\N{check mark} Trade Count Below Threshold')
            self.logger().warn(str(self.orders_attempted_count) +" / "+ str(self.orders_completed_count) +" / "+ str(self.max_num_trade_attempts))
            # 3. Check Wallet UST Balance Above Threshold
            if not self.trade_eval_ust_balance_above_threshold():
                return 
            self.logger().info(u'\N{check mark} UST Balance Above Threshold')
            self.logger().info(u'\N{LATIN SMALL LETTER O WITH STROKE} Current Position is '+str(self.current_position_amount))
            # 4. Prepare Sell Contract
            pool, amount, sellinfo, belief_price, max_spread = await self.trade_generate_sell_contract_values()
            self.logger().info('Contract vars')
            contract_vars = " ".join([str(pool), str(amount), str(json.dumps(sellinfo)), str(belief_price), str(max_spread)])
            self.logger().info(contract_vars)
            # 4. Execute Sell Contract
            if c_map.get("PAPER_TRADE").value == 'True':
                self.logger().info(u'\N{check mark} ------- PAPER TRADE SELL -------: '+ c_map.get("PAPER_TRADE").value)
                self.balance  = await self.terra_service.request_updated_wallet_balance()
                self.logger().info(self.balance)
                return
            else:
                result = self.terra_service.token_swap(pool, amount, sellinfo, belief_price, max_spread)
                self.logger().info("outputting transaction log..")
                self.logger().info(result.txhash)
                self.logger().warn(result.raw_log)
                self.logger().info("transaction complete..")                
                self.balance  = await self.terra_service.request_updated_wallet_balance()

                self.logger().info(self.balance)
                self.orders_completed_count = self.orders_completed_count+1

    async def trade_generate_sell_contract_values(self):
        # Generate Values
        assets = await asyncio.ensure_future(self.terra_service.contract_query(self.pool))
        bal = self.terra_service.get_balance_from_wallet(self.balance, self.terra_service.coin_to_denom(c_map.get("OFFER_ASSET").value))
        amount = int(float(c_map.get("DEFAULT_BASE_TX_SIZE_PERCENTAGE_OF_BAL").value)*bal.amount)
        self.pricing = self.terra_service.get_pair_pricing(self.pool)
        # SELL
        info = []
        beliefPriceStr = ''
        self.logger().info(assets)
        m = c_map.get("TARGET_PAIR").value
        if m == 'Luna-UST': 
            info = assets["assets"][1]['info']
            if 'token0' in self.pricing:
                beliefPriceStr = self.pricing['token0']['price']
        elif m == 'UST-bLuna': 
            info = assets["assets"][0]['info']
            if 'token1' in self.pricing:
                beliefPriceStr = self.pricing['token1']['price']
        elif m == 'UST-bETH': 
            info = assets["assets"][0]['info']
            if 'token1' in self.pricing:
                beliefPriceStr = self.pricing['token1']['price']
        else:
            info = assets["assets"][0]['info']
            if 'token1' in self.pricing:
                beliefPriceStr = self.pricing['token1']['price']
            print("You are running with an Untested token pair, proceed with caution.")    
        belief_price = beliefPriceStr
        print("belief_price")
        print(belief_price)
        max_spread = c_map.get("DEFAULT_MAX_SPREAD").value
        return self.pool, amount, info, belief_price, max_spread

    async def trade_generate_buy_contract_values(self):
        # Generate Values
        assets = await asyncio.ensure_future(self.terra_service.contract_query(self.pool))
        bal = self.terra_service.get_balance_from_wallet(self.balance, self.terra_service.coin_to_denom(c_map.get("OFFER_ASSET").value))
        amount = int(float(c_map.get("DEFAULT_BASE_TX_SIZE_PERCENTAGE_OF_BAL").value)*bal.amount)
        self.pricing = self.terra_service.get_pair_pricing(self.pool)

        # BUY
        info = []
        beliefPriceStr = ''
        self.logger().info(assets)                        
        m = c_map.get("TARGET_PAIR").value
        if m == 'Luna-UST': 
            info = assets["assets"][0]['info']
            if 'token0' in self.pricing:
                beliefPriceStr = self.pricing['token0']['price']            
        elif m == 'UST-bLuna': 
            info = assets["assets"][1]['info']
            if 'token1' in self.pricing:
                beliefPriceStr = self.pricing['token1']['price']
        elif m == 'UST-bETH': 
            info = assets["assets"][1]['info']
            if 'token1' in self.pricing:
                beliefPriceStr = self.pricing['token1']['price']
        else:
            info = assets["assets"][1]['info']
            if 'token1' in self.pricing:
                beliefPriceStr = self.pricing['token1']['price']
            print("You are running with an Untested token pair, proceed with caution.")
        belief_price = beliefPriceStr
        max_spread = c_map.get("DEFAULT_MAX_SPREAD").value
        return self.pool, amount, info, belief_price, max_spread


    def trade_eval_ust_balance_above_threshold(self):
        condition1 = self.terra_service.balance_above_min_threshold(self.balance, self.terra_service.coin_to_denom(c_map.get("BASE_TX_CURRENCY").value), c_map.get("MINIMUM_WALLET_UST_BALANCE").value)
        return condition1

    def trade_eval_num_trades_below_threshold(self):

        return int(self.max_num_trade_attempts) > self.orders_completed_count and int(self.max_num_trade_attempts) > self.orders_attempted_count

    def calculate_moving_averages(self):
        if self.MA_window_size < len(self.oracle_mid_price_series):
            this_window = self.oracle_mid_price_series[len(self.oracle_mid_price_series)-self.MA_window_size-1 : len(self.oracle_mid_price_series)-1 ]
            win_avg = PerformanceMetrics.smart_round(Decimal(sum(this_window) / self.MA_window_size), 8)
            self.oracle_mid_price_series_ma.append(win_avg)
            # print('oracle_mid_price_series_ma:', self.oracle_mid_price_series_ma[len(self.oracle_mid_price_series_ma)-1])

        if self.MA_window_size < len(self.oracle_lower_price_series):
            this_window = self.oracle_lower_price_series[len(self.oracle_lower_price_series)-self.MA_window_size-1 : len(self.oracle_lower_price_series)-1 ]
            win_avg = PerformanceMetrics.smart_round(Decimal(sum(this_window) / self.MA_window_size), 8)
            self.oracle_lower_price_series_ma.append(win_avg)
            # print('oracle_lower_price_series_ma:', self.oracle_lower_price_series_ma[len(self.oracle_lower_price_series_ma)-1])

        if self.MA_window_size < len(self.oracle_upper_price_series):
            this_window = self.oracle_upper_price_series[len(self.oracle_upper_price_series)-self.MA_window_size-1 : len(self.oracle_upper_price_series)-1 ]
            win_avg = PerformanceMetrics.smart_round(Decimal(sum(this_window) / self.MA_window_size),8)
            self.oracle_upper_price_series_ma.append(win_avg)
            # print('oracle_upper_price_series_ma:', self.oracle_upper_price_series_ma[len(self.oracle_upper_price_series_ma)-1])

        if self.MA_window_size < len(self.ask_price_series):
            this_window = self.ask_price_series[len(self.ask_price_series)-self.MA_window_size-1 : len(self.ask_price_series)-1 ]
            win_avg = PerformanceMetrics.smart_round(Decimal(sum(this_window) / self.MA_window_size),8)
            self.ask_price_series_ma.append(win_avg)
            # print('ask_price_series_ma:', self.ask_price_series_ma[len(self.ask_price_series_ma)-1])
        
        print('ma',len(self.ask_price_series_ma), len(self.ask_price_series))
        
    def update_buy_params(self, pool, pricing, wallet_ask_asset_balance):
        self.pool = pool 
        self.pricing = pricing
        self.current_position_amount = wallet_ask_asset_balance
        
    def eval_pricing(self, terra_ask_pricing, oracle_buy_price, oracle_sell_price, oracle_mid_price, balance):
        print('eval:','terra_ask_pricing', 'oracle_buy_price', 'oracle_sell_price')
        print(terra_ask_pricing, oracle_buy_price, oracle_sell_price, oracle_mid_price)
        self.oracle_sell_price = oracle_sell_price
        self.oracle_buy_price = oracle_buy_price
        self.oracle_mid_price = oracle_mid_price
        self.ask_pricing = terra_ask_pricing
        self.balance = balance
        # Upper
        if len(self.oracle_upper_price_series) > self.MA_NUM_TICKS:
            self.oracle_upper_price_series.pop(0)
        self.oracle_upper_price_series.append(oracle_sell_price)
        # Lower
        if len(self.oracle_lower_price_series) > self.MA_NUM_TICKS:
            self.oracle_lower_price_series.pop(0)
        self.oracle_lower_price_series.append(oracle_buy_price)
        # Mid
        if len(self.oracle_mid_price_series) > self.MA_NUM_TICKS:
            self.oracle_mid_price_series.pop(0)
        self.oracle_mid_price_series.append(oracle_mid_price)        
        # Ask
        if len(self.ask_price_series) > self.MA_NUM_TICKS:
            self.ask_price_series.pop(0)
        self.ask_price_series.append(terra_ask_pricing)
        self.calculate_position()
    