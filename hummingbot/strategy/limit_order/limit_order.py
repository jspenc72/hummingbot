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

class LimitOrder(StrategyPyBase):
    # We use StrategyPyBase to inherit the structure. We also 
    # create a logger object before adding a constructor to the class. 
    @classmethod
    def logger(cls) -> HummingbotLogger:
        global hws_logger
        if hws_logger is None:
            hws_logger = logging.getLogger(__name__)
        return hws_logger

    def __init__(self,
                 market_info: MarketTradingPairTuple,
                 terra_client: LCDClient,
                 offer_target: string,
                 ask_target: string,
                 token_target: string, 
                 token_pair,
                 token_pair_asset_info
                 ):

        super().__init__()

        self._market_info = market_info
        self._connector_ready = False
        self._order_completed = False
        self._tick_count = 0
        self._orders_completed_count = 0
        self._order_attempted = False
        self._orders_attempted_count = 0
        self.is_coin_pair = False
        self.is_token_pair = False
        self.add_markets([market_info.market])
        self.terra_client = terra_client
        self.offer_target = offer_target 
        self.ask_target = ask_target 
        self.token_target = token_target
        self.token_pair = token_pair
        self.token_pair_asset_info = token_pair_asset_info
        # Setup terra client connection to columbus-5 (mainnet)
        # Should parameterize and read id and url from chains.json
        self.terra = LCDClient(chain_id="columbus-5", url="https://lcd.terra.dev")
        self.utils = LimitOrderUtils(self.terra)
        # 
        self.tokens = self.utils.get_tokens()

        SECRET_TERRA_MNEMONIC = os.getenv('SECRET_TERRA_MNEMONIC')
        if os.getenv("SECRET_TERRA_MNEMONIC") is not None:
            self.mk = MnemonicKey(mnemonic=SECRET_TERRA_MNEMONIC)
            self.wallet = self.terra.wallet(self.mk)
 
        else:
            self.logger().info("Something Went Wrong. Shutting Hummingbot down now...")
            time.sleep(3)
            sys.exit("Something Went Wrong!")
       
    # After initializing the required variables, we define the tick method. 
    # The tick method is the entry point for the strategy. 
    def check_run_params(self): 
        # Get Config Values

        MAX_NUM_TRADE_ATTEMPTS = c_map.get("MAX_NUM_TRADE_ATTEMPTS").value
        MINIMUM_WALLET_UST_BALANCE = c_map.get("MINIMUM_WALLET_UST_BALANCE").value
        ORDER_TYPE = c_map.get("ORDER_TYPE").value
        BASE_LIMIT_PRICE = c_map.get("BASE_LIMIT_PRICE").value
        BASE_TX_CURRENCY = c_map.get("BASE_TX_CURRENCY").value
        DEFAULT_BASE_TX_SIZE_PERCENTAGE_OF_BAL = c_map.get("DEFAULT_BASE_TX_SIZE_PERCENTAGE_OF_BAL").value
        DEFAULT_MAX_SPREAD = c_map.get("DEFAULT_MAX_SPREAD").value
        USE_MAX_TRANSACTION_SIZE = c_map.get("USE_MAX_TRANSACTION_SIZE").value
        
        # Check run conditions
        balance = self.terra.bank.balance(self.mk.acc_address)
        condition1 = self.utils.balance_above_min_threshold(balance, self.utils.coin_to_denom(BASE_TX_CURRENCY), MINIMUM_WALLET_UST_BALANCE)
        self.logger().info("balance_above_min_threshold PASS: "+ str(condition1))
        # condition2 = self.utils.check_base_currency(self.offer_target, BASE_TX_CURRENCY)
        # print("check_base_currency PASS: ", condition2)
        condition3 = self.utils.number_of_trades_below_threshold(self._orders_attempted_count, MAX_NUM_TRADE_ATTEMPTS)
        self.logger().info("number_of_trades_below_threshold PASS: "+ str(condition3))
        self.logger().info("orders completed / orders attempted / ticks processed")
        self.logger().info(str(self._orders_completed_count)+" / "+str(self._orders_attempted_count)+" / "+str(self._tick_count))
        return condition1 and condition3
        
    def tick(self, timestamp: float):
        self._tick_count = self._tick_count+1
        
        self.logger().info("tick: "+str(self._tick_count)+" eval: "+ self.ask_target +" > "+ self.offer_target + " tc: "+ self.token_target)
        
        if not self._connector_ready:
            self._connector_ready = self._market_info.market.ready
            if not self._connector_ready:
                self.logger().warning(f"{self._market_info.market.name} is not ready. Please wait...")
                return
            else: 
                self.logger().warning(f"{self._market_info.market.name} is ready. Trading started")
        else:
            
            balance = self.terra.bank.balance(self.mk.acc_address)
            tx_size = self.utils.get_base_tx_size_from_balance(balance, self.utils.coin_to_denom(c_map.get("BASE_TX_CURRENCY").value), c_map.get("DEFAULT_BASE_TX_SIZE_PERCENTAGE_OF_BAL").value)

            if tx_size == 0:
                self.logger().warning(f"computed transaction size is 0, check wallet balance: ")
                self.logger().warning(tx_size)
                return 

            if self.token_target == '':
                self.is_coin_pair = True
                # Evaluate Trade
                offset, trade = self.evaluate_coin_pair_offset(tx_size)
                if trade == False:
                    self.logger().info("Current Limit Offset: ", offset)
                    return

            elif self.token_target != '':    
                self.is_token_pair = True
                offset, trade = self.evaluate_token_pair_offset()
                if trade == False:
                    self.logger().info("Current Limit Offset: ", offset)
                    return                    

            if not self._order_completed or not self._order_attempted:
                if self.check_run_params():                            
                    self._order_attempted = True
                    # Handle if coin pair is coin
                    if self.is_coin_pair:
                        offset, trade  = self.evaluate_coin_pair_offset(tx_size)
                        
                        if trade == False:
                            self.logger().info("Limit Offset: ", offset)
                            return

                        # swap = MsgSwap(self.mk.acc_address, rate, 'uusd')
                        swap = MsgSwap(self.mk.acc_address, str(tx_size)+''+self.offer_target, self.ask_target)
                        self.logger().info(swap)
                        sequence = self.wallet.sequence()
                        tx = self.wallet.create_and_sign_tx(
                            msgs=[swap],
                            gas_prices='2'+self.offer_target,
                            gas_adjustment='1.5',
                            sequence=sequence
                        )
                        self._orders_attempted_count = self._orders_attempted_count+1
                        result = self.terra.tx.broadcast(tx)

                        self.logger().info("coin transaction complete!")
                        self.logger().info("coin transaction log!")
                        self.logger().info(result.raw_log)
                        self.logger().info("coin transaction hash: "+ result.txhash)
                        self._order_completed = True
                        self._orders_completed_count = self._orders_completed_count+1
                        balance = self.terra.bank.balance(self.mk.acc_address)
                        self.logger().info(balance)
                    # Handle if coin pair is token
                    if self.is_token_pair:
                        pool = "terra1j66jatn3k50hjtg2xemnjm8s7y8dws9xqa5y8w" # uluna <> bLuna
                        # Find contract id
                        pool = self.token_target
                        self.logger().info("Requesting pool assets")
                        assets = self.terra.wasm.contract_query(pool, { "pool": {} })
                        self.logger().info(assets)                        
                        asset0 = assets["assets"][0]['amount']
                        asset0Int = int(asset0)
                        asset1 = assets["assets"][1]['amount']
                        asset1Int = int(asset1)
                        beliefPrice = asset0Int / asset1Int                        
                        beliefPriceStr = str(beliefPrice)                        
                        self.logger().info("Computed belief_price: "+str(beliefPrice))
                        self.logger().info("Preparing order with beliefPrice: "+str(beliefPrice)+" "+str(tx_size)+" "+ self.offer_target+" ")
                        if tx_size == 0:
                            self.logger().info("Unable to execute trade of size: "+str(tx_size))
                        
                        targettoken = self.utils.parse_token_from_pair_pricing(self.pricing, c_map.get("BASE_TX_CURRENCY").value)
                        ratio = targettoken['price']
                        balance = self.utils.get_balance_from_wallet(balance, self.utils.coin_to_denom(c_map.get("BASE_TX_CURRENCY").value))
                        # Total balance in BASE CURRENCY
                        amt = balance.amount*10**-6
                        # Configured Tradable balance in BASE CURRENCY
                        tradableamt = int(float(c_map.get("DEFAULT_BASE_TX_SIZE_PERCENTAGE_OF_BAL").value)*balance.amount)
                        self.logger().info('token_pair')
                        self.logger().info(self.token_pair)
                        # Convert to target token using ratio
                        final_tx_size = int(amt*float(ratio)*10**6)
                        # native_token = self.utils.parse_native_token_from_token_pair_asset(self.token_pair_asset_info)
                        # print(native_token)
                        # return 

                        sellinfo = []
                        m = c_map.get("TARGET_PAIR").value
                        if m == 'Luna-UST': 
                            sellinfo = assets["assets"][0]['info']
                        elif m == 'UST-bLuna': 
                            sellinfo = assets["assets"][1]['info']
                            if 'token1' in self.pricing:
                                beliefPriceStr = self.pricing['token1']['price']
                        elif m == 'UST-bETH': 
                            sellinfo = assets["assets"][1]['info']
                            if 'token1' in self.pricing:
                                beliefPriceStr = self.pricing['token1']['price']
                        else:
                            sellinfo = assets["assets"][1]['info']
                            if 'token1' in self.pricing:
                                beliefPriceStr = self.pricing['token1']['price']
                            self.logger().info("You are running with an Untested token pair, proceed with caution.")
                        print(sellinfo)
                        swp = {
                                "swap": {
                                    "max_spread": c_map.get("DEFAULT_MAX_SPREAD").value,
                                    "offer_asset": {
                                        "info": sellinfo,
                                        "amount": str(tradableamt)
                                    },
                                    "belief_price": beliefPriceStr
                                }
                            }
                            
                        # SELL 
                        # msg = base64({"swap":{"max_spread":"0.005","belief_price":"0.000312527301842629"}})
                        # 
                        # {
                        #   "send": {
                        #       "msg": "eyJzd2FwIjp7Im1heF9zcHJlYWQiOiIwLjAwNSIsImJlbGllZl9wcmljZSI6IjAuMDAwMzEyNTI3MzAxODQyNjI5In19",
                        #       "amount": "2293",
                        #       "contract": "terra1c0afrdc5253tkp5wt7rxhuj42xwyf2lcre0s7c"
                        #   }
                        # }

                        self.logger().info(swp)
                        swap = MsgExecuteContract(
                            sender=self.wallet.key.acc_address,
                            contract=pool,
                            execute_msg=swp,
                            coins=Coins.from_str(str(tradableamt)+''+sellinfo['native_token']['denom']),
                        )
                        self.logger().info(swap)
                        tx = self.wallet.create_and_sign_tx(
                            msgs=[swap], 
                            gas_prices='2'+self.utils.coin_to_denom(c_map.get("BASE_TX_CURRENCY").value),
                            gas_adjustment='1.5',
                            sequence = self.wallet.sequence()
                        )                        
                        self.logger().info(tx)
                        self._orders_attempted_count = self._orders_attempted_count+1
                        # return 
                        result = self.terra.tx.broadcast(tx)
                        self.logger().info("token transaction log!")
                        self.logger().info(result.raw_log)
                        self.logger().info("token transaction complete!")
                        self.logger().info(result.txhash)
                        balance = self.terra.bank.balance(self.mk.acc_address)
                        self.logger().info(balance)
                        self._order_completed = True
                        self._orders_completed_count = self._orders_completed_count+1

                    self._order_attempted = True

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
            self.logger().info("Buy: offset, price, trade: "+str(offset)+" "+str(price)+" "+str(trade))
            self.logger().info("Buy: offset, price, trade: "+str(offset*10**-6)+" "+str(price*10**-6)+" "+str(trade))
        else:
            offset, price, trade, token = self.utils.get_token_sell_limit_order_offset(self.pricing, c_map.get("BASE_LIMIT_PRICE").value, target)
            self.logger().info(token)
            self.logger().info("Sell: offset, price, trade: "+str(offset*10**-6)+" "+str(price*10**-6)+" "+str(trade))
        return offset, trade

    def evaluate_coin_pair_offset(self, tx_size):
        int_coin = Coin(self.offer_target, tx_size)
        rate = self.terra.market.swap_rate(int_coin, self.ask_target)
        self.logger().info("Limit Order: Simulating Swap before trade")
        self.logger().info("swap: "+str(tx_size) + self.offer_target +" > "+ self.ask_target)
        self.logger().info("current rate: ")
        self.logger().info(rate)

        if c_map.get("ORDER_TYPE").value == "BUY":
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


    # Emit a log message when the order completes
    def did_complete_buy_order(self, order_completed_event):
        self.logger().info(f"Your limit buy order {order_completed_event.order_id} has been executed")
        self.logger().info(order_completed_event)

    async def get_order_price(self, market, trading_pair: str, is_buy: bool, amount: Decimal):
        return await market.get_quote_price(trading_pair, True, 1.0)

    async def format_status(self) -> str:
        """
        Returns a status string formatted to display nicely on terminal. The strings composes of 4 parts: markets,
        assets, profitability and warnings(if any).
        """
        status = ''
        rows = []
        sections = []
        # if self._arb_proposals is None:
        #     return "  The strategy is not ready, please try again later."
        # active_orders = self.market_info_to_active_orders.get(self._market_info, [])
        # SECTION BOT CONFIG
        configcols = [["MAX_NUM_TRADE_ATTEMPTS: ", c_map.get("MAX_NUM_TRADE_ATTEMPTS").value],["MINIMUM_WALLET_UST_BALANCE: ", c_map.get("MINIMUM_WALLET_UST_BALANCE").value],
                            ["ORDER_TYPE: ", c_map.get("ORDER_TYPE").value],
                            ["BASE_LIMIT_PRICE: ", c_map.get("BASE_LIMIT_PRICE").value],
                            ["BASE_TX_CURRENCY: ", c_map.get("BASE_TX_CURRENCY").value],
                            ["DEFAULT_BASE_TX_SIZE_PERCENTAGE_OF_BAL: ", c_map.get("DEFAULT_BASE_TX_SIZE_PERCENTAGE_OF_BAL").value],
                            ["DEFAULT_MAX_SPREAD: ", c_map.get("DEFAULT_MAX_SPREAD").value],
                            ["USE_MAX_TRANSACTION_SIZE: ", c_map.get("USE_MAX_TRANSACTION_SIZE").value]]
        




        for value in configcols: 
            row = " ".join(value)
            rows.append(row)

        p = self.pricing
        if 'liquidities' in p:
            del p['liquidities']
        if 'volumes' in p:
            del p['volumes']

        jsonformattedstring = json.dumps(p, indent=2)
        rows.append(jsonformattedstring)

        rows.append("orders completed / orders attempted / ticks processed")
        rows.append(str(self._orders_completed_count)+" / "+str(self._orders_attempted_count)+" / "+str(self._tick_count))
        
        rows.append("Limit Buy: offset --- price ---- trade")
        rows.append(str(self.current_offset)+" ---- "+str(self.current_price)+" ---- "+str(self.current_trade))


        return "\n".join(rows)