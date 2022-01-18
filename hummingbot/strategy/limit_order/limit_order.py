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
                 token_pair
                 ):

        super().__init__()

        self._market_info = market_info
        self._connector_ready = False
        self._order_completed = False
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
        print("balance_above_min_threshold PASS: ", condition1)
        # condition2 = self.utils.check_base_currency(self.offer_target, BASE_TX_CURRENCY)
        # print("check_base_currency PASS: ", condition2)
        condition3 = self.utils.number_of_trades_below_threshold(self._orders_completed_count, MAX_NUM_TRADE_ATTEMPTS)
        print("number_of_trades_below_threshold PASS: ", condition3)
        return condition1 and condition3
        
    def tick(self, timestamp: float):

        if not self._connector_ready:
            self._connector_ready = self._market_info.market.ready
            if not self._connector_ready:
                self.logger().warning(f"{self._market_info.market.name} is not ready. Please wait...")
                return
            else:
                self.logger().warning(f"{self._market_info.market.name} is ready. Trading started")
                self.logger().info("{timestamp} Evaluate Limit Order: "+ self.ask_target +" > "+ self.offer_target + " token: "+ self.token_target)
                denoms = self.terra.oracle.active_denoms()
                rates = self.terra.oracle.exchange_rates()
                balance = self.terra.bank.balance(self.mk.acc_address)
                tx_size = self.utils.get_base_tx_size_from_balance(balance, self.utils.coin_to_denom(c_map.get("BASE_TX_CURRENCY").value), c_map.get("DEFAULT_BASE_TX_SIZE_PERCENTAGE_OF_BAL").value)

                if tx_size == 0:
                    self.logger().warning(f"computed transaction size is 0, check wallet balance", balance)
                    return 

                if self.token_target == '':
                    self.is_coin_pair = True
                    # Evaluate Trade
                    offset, trade = self.evaluate_coin_pair_offset(tx_size)
                    if trade == False:
                        print("Current Limit Offset: ", offset)
                        return

                elif self.token_target != '':    
                    self.is_token_pair = True
                    offset, trade = self.evaluate_token_pair_offset()
                    if trade == False:
                        print("Current Limit Offset: ", offset)
                        return                    

                if not self._order_completed or not self._order_attempted:
                    if self.check_run_params():                            
                        self._order_attempted = True
                        # Handle if coin pair is coin
                        if self.is_coin_pair:
                            offset, trade  = self.evaluate_coin_pair_offset(tx_size)
                            
                            if trade == False:
                                print("Limit Offset: ", offset)
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
                            print("handle token")
                            pool = "terra1j66jatn3k50hjtg2xemnjm8s7y8dws9xqa5y8w" # uluna <> bLuna
                            # Find contract id
                            pool = self.token_target

                            assets = self.terra.wasm.contract_query(pool, { "pool": {} })
                            self.logger().info("assets")
                            print(assets)
                            time.sleep(1)
                            asset0 = assets["assets"][0]['amount']
                            asset0Int = int(asset0)
                            asset1 = assets["assets"][1]['amount']
                            asset1Int = int(asset1)

                            beliefPrice = asset0Int / asset1Int
                            beliefPriceStr = str(beliefPrice)
                            self.logger().info("beliefPrice")
                            self.logger().info(beliefPrice)
                            self.logger().info(beliefPriceStr)
                            tx_size = self.utils.get_base_tx_size_from_balance(balance, self.offer_target, c_map.get("DEFAULT_BASE_TX_SIZE_PERCENTAGE_OF_BAL").value)

                            swp = {
                                        "swap": {
                                            "max_spread": "0.005",
                                            "offer_asset": {
                                                "info": {
                                                    "native_token": {
                                                        "denom": self.offer_target
                                                    }
                                                },
                                                "amount": tx_size
                                            },
                                            "belief_price": beliefPriceStr
                                        }
                                }
                                
                            self.logger().info(swp)
                            swap = MsgExecuteContract(
                                sender=self.wallet.key.acc_address,
                                contract=pool,
                                execute_msg=swp,
                                coins=Coins.from_str(str(tx_size)+''+self.offer_target),
                            )

                            tx = self.wallet.create_and_sign_tx(
                                msgs=[swap], 
                                gas_prices='2'+self.offer_target,
                                gas_adjustment='1.5',
                                sequence = self.wallet.sequence()
                            )
                            self.logger().info(tx)
                            self._orders_attempted_count = self._orders_attempted_count+1
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
        pricing = self.utils.get_pair_pricing(self.token_target)        
        if c_map.get("ORDER_TYPE").value == "BUY":
            offset, price, trade = self.utils.get_token_buy_limit_order_offset(pricing, c_map.get("BASE_LIMIT_PRICE").value)
            print("Buy: offset, price, trade", offset, price, trade)
        else:
            offset, price, trade = self.utils.get_token_sell_limit_order_offset(pricing, c_map.get("BASE_LIMIT_PRICE").value)
            print("Sell: offset, price, trade ", offset, price, trade)
        return offset, trade


    def evaluate_coin_pair_offset(self, tx_size):
        int_coin = Coin(self.offer_target, tx_size)
        rate = self.terra.market.swap_rate(int_coin, self.ask_target)
        self.logger().info("Limit Order: Simulating Swap before trade")
        self.logger().info("swap: "+str(tx_size) + self.offer_target +" > "+ self.ask_target)
        self.logger().info("current rate: ")
        self.logger().info(rate)

        if c_map.get("ORDER_TYPE").value == "BUY":
            offset, trade = self.utils.get_coin_buy_limit_order_offset(rate, c_map.get("BASE_LIMIT_PRICE").value)
        else:
            offset, trade = self.utils.get_coin_sell_limit_order_offset(rate, c_map.get("BASE_LIMIT_PRICE").value)
        
        if trade == False:
            print("Limit Offset: ", offset)
        
        return offset, trade  


    # Emit a log message when the order completes
    def did_complete_buy_order(self, order_completed_event):
        self.logger().info(f"Your limit buy order {order_completed_event.order_id} has been executed")
        self.logger().info(order_completed_event)

    async def get_order_price(self, market, trading_pair: str, is_buy: bool, amount: Decimal):
        return await market.get_quote_price(trading_pair, True, 1.0)

