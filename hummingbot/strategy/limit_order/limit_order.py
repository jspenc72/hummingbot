#!/usr/bin/env python

from decimal import Decimal
import logging
import asyncio

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
                 ):

        super().__init__()
        self._market_info = market_info
        self._connector_ready = False
        self._order_completed = False
        self.add_markets([market_info.market])

    # After initializing the required variables, we define the tick method. 
    # The tick method is the entry point for the strategy. 
    def tick(self, timestamp: float):
        if not self._connector_ready:
            self._connector_ready = self._market_info.market.ready
            if not self._connector_ready:
                self.logger().warning(f"{self._market_info.market.name} is not ready. Please wait...")
                return
            else:
                self.logger().warning(f"{self._market_info.market.name} is ready. Trading started")

        if not self._order_completed:
            self.logger().info("Limit Order: New Tick!")
            self.logger().info("Quote Pairs!")
            pairs = ["ANC-UST", "bLUNA-LUNA", "MINE-UST", "LUNA-UST", "MIR-UST", "mIAU-UST", "mQQQ-UST", "mAAPL-UST", "STT-UST", "mMSFT-UST", "mSLV-UST", "VKR-UST", "mGOOGL-UST", "mNFLX-UST", "mBABA-UST", "mAMZN-UST", "mUSO-UST", "mVIXY-UST", "mTSLA-UST", "nLuna-Psi", "Psi-UST" ]
            self.logger().info(pairs)

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



















            for pair in pairs: 
                self.logger().info(f"Preparing limit buy order for pair: " + pair)
                self.logger().info(f"ERROR: cannot complete transaction not enough funds.")
                
            # self.logger().info(f"Preparied limit buy order {order_id}")
            self._order_completed = True

    # Emit a log message when the order completes
    def did_complete_buy_order(self, order_completed_event):
        self.logger().info(f"Your limit buy order {order_completed_event.order_id} has been executed")
        self.logger().info(order_completed_event)

    async def get_order_price(self, market, trading_pair: str, is_buy: bool, amount: Decimal):
        return await market.get_quote_price(trading_pair, True, 1.0)
        