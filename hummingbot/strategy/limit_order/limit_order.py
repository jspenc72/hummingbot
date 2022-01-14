#!/usr/bin/env python
from decimal import Decimal
import os
import sys
import json
import logging
import asyncio
import time

from terra_sdk.client.lcd import LCDClient
from terra_sdk.key.mnemonic import MnemonicKey
from terra_sdk.core.market import MsgSwap
from terra_sdk.client.lcd.api.oracle import OracleAPI
from terra_sdk.client.lcd.api.staking import StakingAPI
from terra_sdk.client.lcd.api.wasm import WasmAPI
from terra_sdk.core.wasm import MsgStoreCode, MsgInstantiateContract, MsgExecuteContract
from terra_sdk.core.auth.data.tx import StdFee
from terra_sdk.core import Coin, Coins

from hummingbot.core.event.events import OrderType
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.strategy_py_base import StrategyPyBase

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
                 terra_ibc_tokens: json,
                 terra_cw20_tokens: json,                 
                 ):

        super().__init__()
        self._market_info = market_info
        self._connector_ready = False
        self._order_completed = False
        self._order_attempted = False
        self.is_coin_pair = False
        self.is_token_pair = False
        self.add_markets([market_info.market])
        self.terra_client = terra_client
        self.terra_ibc_tokens = terra_ibc_tokens
        self.terra_cw20_tokens = terra_cw20_tokens
        self.terra = LCDClient(chain_id="columbus-5", url="https://lcd.terra.dev")
        SECRET_TERRA_MNEMONIC = os.getenv('SECRET_TERRA_MNEMONIC')
        if os.getenv("SECRET_TERRA_MNEMONIC") is not None:
            self.mk = MnemonicKey(mnemonic=SECRET_TERRA_MNEMONIC)
            self.wallet = self.terra.wallet(self.mk)
            balance = self.terra.bank.balance(self.mk.acc_address)
            self.logger().info(balance)             
            self.logger().info("Retrieving Terra Wallet Balance")
            balance = self.terra.bank.balance(self.mk.acc_address)
            self.logger().info(balance)    
        else:
            self.logger().info("Something Went Wrong. Shutting Hummingbot down now...")
            time.sleep(3)
            sys.exit("Something Went Wrong!")


       
    # After initializing the required variables, we define the tick method. 
    # The tick method is the entry point for the strategy. 
    def tick(self, timestamp: float):
        # Setup terra client connection to columbus-5 (mainnet)
        # Should parameterize and read id and url from chains.json
        denoms = self.terra.oracle.active_denoms()
        rates = self.terra.oracle.exchange_rates()

        if not self._connector_ready:
            self._connector_ready = self._market_info.market.ready
            if not self._connector_ready:
                self.logger().warning(f"{self._market_info.market.name} is not ready. Please wait...")
                return
            else:
                self.logger().warning(f"{self._market_info.market.name} is ready. Trading started")

        if not self._order_completed or not self._order_attempted:
            self._order_attempted = True
            self.logger().info(denoms)
            self.logger().info(rates)            
            self.logger().info(self.mk.acc_address)
            self.logger().info("Limit Order: New Tick!")
            self.logger().info("Quote Pairs!")
            # https://assets.terra.money/cw20/tokens.json
            # https://assets.terra.money/ibc/tokens.json

            pairs = ["ANC-UST", "bLUNA-LUNA", "MINE-UST", "LUNA-UST", "MIR-UST", "mIAU-UST", "mQQQ-UST", "mAAPL-UST", "STT-UST", "mMSFT-UST", "mSLV-UST", "VKR-UST", "mGOOGL-UST", "mNFLX-UST", "mBABA-UST", "mAMZN-UST", "mUSO-UST", "mVIXY-UST", "mTSLA-UST", "nLuna-Psi", "Psi-UST" ]
            swapdenoms = ['uaud', 'ucad', 'uchf', 'ucny', 'udkk', 'ueur', 'ugbp', 'uhkd', 'uidr', 'uinr', 'ujpy', 'ukrw', 'umnt', 'uphp', 'usdr', 'usek', 'usgd', 'uthb', 'uusd']
            self.logger().info(pairs)
            self.logger().info(swapdenoms)

            # Check if coin pair is coin
            if self.is_coin_pair:
                self.logger().info("Limit Order: Simulating Swap before trade")
                int_coin = Coin.from_str("1000000uusd")
                rate = self.terra.market.swap_rate(int_coin, 'uluna')
                self.logger().info(rate)
                self.logger().info("Limit Order: Coin Pair!")
                
                # swap = MsgSwap(self.mk.acc_address, rate, 'uusd')
                swap = MsgSwap(self.mk.acc_address, '1000000uusd', 'uluna')
                sequence = self.wallet.sequence()
                tx = self.wallet.create_and_sign_tx(
                    msgs=[swap],
                    gas_prices='2uusd',
                    gas_adjustment='1.5',                    
                    sequence=sequence
                )

                # tx = self.wallet.create_and_sign_tx(
                #     msgs=[swap],
                    # gas_prices='2uluna',
                    # gas_adjustment='1.5',
                #     denoms=['uusd', 'uluna']
                # )
                
                result = self.terra.tx.broadcast(tx)
                self.logger().info("coin transaction complete!")
                self.logger().info("coin transaction log!")
                self.logger().info(result.raw_log)
                self.logger().info("coin transaction hash: "+ result.txhash)
                self._order_completed = True
                balance = self.terra.bank.balance(self.mk.acc_address)
                self.logger().info(balance)
            # Check if coin pair is token
            if self.is_token_pair:
                pool = "terra1tndcaqxkpc5ce9qee5ggqf430mr2z3pefe5wj6" # UST <> uluna

                assets = self.terra.wasm.contract_query(pool, { "pool": {} })

                beliefPrice = assets[0].amount / assets[1].amount
                self.logger().info(beliefPrice)

                execute = MsgExecuteContract(
                    self.wallet.key.acc_address,
                    pool, 
                    {
                        "swap": {
                            "max_spread": "0.01",
                            "offer_asset": {
                                "info": {
                                    "native_token": {
                                        "denom": "uusd",
                                    },
                                },
                                "amount": "1000000",
                            },
                            "belief_price": beliefPrice,
                        },
                    },
                    {"uluna": 100000},
                )

                tx = self.wallet.create_and_sign_tx(
                    msgs=[execute], fee=StdFee(1000000, Coins(uluna=1000000))
                )
                result = self.terra.tx.broadcast(tx)
                self.logger().info("token transaction complete!")
                self.logger().info(result.txhash)
                balance = self.terra.bank.balance(self.mk.acc_address)
                self.logger().info(balance)
                self._order_completed = True

            # print(terra.tendermint.node_info())

            # 
            # mk.mnemonic()


            # delegations = self.terra.staking.validators() 
            # self.logger().info(delegations)
            # ublunarate = terra.oracle.exchange_rate('ubluna')
            # self.logger().info(ublunarate)


            # self.logger().info(quote_pice)
            market = self.active_markets[0]
            # quote_pice = self._market_info.market.get_quote_price()
            # quote_price = await self.get_order_price(market, pairs[3], True, 1.0)
            print(self._market_info)
            # self.logger().info(self._market_info)
            # The get_mid_price method gets the mid price of the coin and
            # stores it. This method is derived from the MarketTradingPairTuple class.

            # mid_price = self._market_info.get_quote_price() 
            # self.logger().info("New Tick!")
            # self.logger().info(mid_price)


            # The buy_with_specific_market method executes the trade for you. This     
            # method is derived from the Strategy_base class. 

            # order_id = self.buy_with_specific_market(
            #     self._market_info,  # market_trading_pair_tuple
            #     Decimal("0.005"),   # amount
            #     OrderType.LIMIT,    # order_type
            #     -0.01           # price
            # )



            # for pair in pairs: 
            #     self.logger().info(f"Preparing limit buy order for pair: " + pair)
            #     self.logger().info(f"ERROR: cannot complete transaction not enough funds.")
                
            # self.logger().info(f"Preparied limit buy order {order_id}")
            self._order_completed = True

    # Emit a log message when the order completes
    def did_complete_buy_order(self, order_completed_event):
        self.logger().info(f"Your limit buy order {order_completed_event.order_id} has been executed")
        self.logger().info(order_completed_event)

    async def get_order_price(self, market, trading_pair: str, is_buy: bool, amount: Decimal):
        return await market.get_quote_price(trading_pair, True, 1.0)
        