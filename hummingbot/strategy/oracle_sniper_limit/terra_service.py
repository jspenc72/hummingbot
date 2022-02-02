import asyncio
import requests
import json
import os 
import time
import sys
from terra_sdk.client.lcd import LCDClient, AsyncLCDClient
from terra_sdk.key.mnemonic import MnemonicKey
from terra_sdk.core import Coin, Coins
from terra_sdk.core.bank.msgs import MsgSend
from terra_sdk.core.market import MsgSwap
from terra_sdk.client.lcd.api.oracle import OracleAPI
from terra_sdk.client.lcd.api.staking import StakingAPI
from terra_sdk.client.lcd.api.wasm import WasmAPI
from terra_sdk.core.wasm import MsgStoreCode, MsgInstantiateContract, MsgExecuteContract
from terra_sdk.core.auth.data.tx import StdFee

from hummingbot.strategy.oracle_sniper_limit.singleton import Singleton
from hummingbot.core.utils.async_utils import safe_ensure_future

@Singleton
class TerraService():
    # We use StrategyPyBase to inherit the structure. We also 
    # create a logger object before adding a constructor to the class. 

    def __init__(self):
        self.mk = None
        self.wallet = None
        self.terra = None
        self._main_task = None
        self.is_ready = True
        if self._main_task is None or self._main_task.done():
            self._main_task = safe_ensure_future(self.main())

    async def main(self):
        await self.create_client()

    def test(self):
        print("test")

    async def create_client(self):
        print("creating terraswap client...")
        res = self.request_updated_gas_prices()
        async with AsyncLCDClient(chain_id="columbus-5", url="https://lcd.terra.dev", gas_prices=Coins(res), gas_adjustment="1.4") as terra:
            self.terra = terra            
        
            SECRET_TERRA_MNEMONIC = os.getenv('SECRET_TERRA_MNEMONIC')
            if os.getenv("SECRET_TERRA_MNEMONIC") is not None:
                self.mk = MnemonicKey(mnemonic=SECRET_TERRA_MNEMONIC)
                self.wallet = self.terra.wallet(self.mk)
                bal = await self.request_updated_wallet_balance()
            else:
                self.logger().info("Something Went Wrong. Shutting Hummingbot down now...")
                time.sleep(3)
                sys.exit("Something Went Wrong!")        
            self.load_files()
            self.pull_api_info()

    async def request_updated_wallet_balance(self):
        print("getting wallet balance...")
        self.balance = await self.terra.bank.balance(self.mk.acc_address)
        return self.balance

    # Public api.terraswap.io Library Methods
    def request_updated_gas_prices(self):
        print("requesting gas prices...")
        self.gas_prices = requests.get("https://fcd.terra.dev/v1/txs/gas_prices").json()

    def pull_api_info(self):
        self.request_cw20_tokens()
        self.request_cw20_pairs()
        self.request_asset_info_pairs()


    def request_cw20_tokens(self):
        self.cw20_tokens = requests.get('https://api.terraswap.io/tokens').json()
        return self.cw20_tokens

    def request_cw20_pairs(self):
        self.cw20_pairs = requests.get('https://api.terraswap.io/dashboard/pairs').json()
        return self.cw20_pairs        

    def request_asset_info_pairs(self):
        self.asset_info_pairs = requests.get('https://api.terraswap.io/pairs').json()
        return self.asset_info_pairs                

    def load_files(self):
        self.open_cw20()
        self.open_ibc()
        self.open_fcw20pairs()
        self.open_coin_to_denom()
        
    # local terraswap methods
    def open_cw20(self):
        self.cw20_json = json.load(open(os.getcwd()+'/hummingbot/strategy/limit_order/cw20.json'))
        return self.cw20_json

    def open_ibc(self):
        self.ibc_json = json.load(open(os.getcwd()+'/hummingbot/strategy/limit_order/ibc.json'))
        return self.ibc_json

    def open_fcw20pairs(self):
        self.cw20pairs_json = json.load(open(os.getcwd()+'/hummingbot/strategy/limit_order/pairs.dex.json'))
        return self.cw20pairs_json

    def open_coin_to_denom(self):
        self.coin_to_denom_json = json.load(open(os.getcwd()+'/hummingbot/strategy/limit_order/coin_to_denom.json'))
        return self.coin_to_denom_json

    # Contract Methods
    async def broadcast_tx(self, tx):
        result = self.terra.tx.broadcast(tx)
    
    async def send(self, recipient_wallet_addr, coins):
        wallet = self.terra.wallet(self.mk)
        account_number = await wallet.account_number()
        tx = await wallet.create_and_sign_tx(
            msgs=[MsgSend(wallet.key.acc_address, recipient_wallet_addr, coins)]
        )
        result = self.broadcast_tx(tx)

    async def coin_swap(self, tx_size, offer_target, ask_target):
        # Get reference to wallet 
        wallet = self.terra.wallet(self.mk)
        account_number = await wallet.account_number()
        swap = MsgSwap(self.mk.acc_address, str(tx_size)+''+offer_target, ask_target)

        sequence = self.wallet.sequence()
        tx = await wallet.create_and_sign_tx(
                            msgs=[swap],
                            gas_prices=Coins(self.gas_prices),
                            gas_adjustment='1.4',
                            sequence=sequence
                        )
        result = self.broadcast_tx(tx)

    async def token_swap(self, pool, amount, sellinfo, belief_price, max_spread=0.5):
        # Get reference to wallet 
        wallet = self.terra.wallet(self.mk)
        account_number = await wallet.account_number()
        swp = {
                "swap": {
                    "max_spread": max_spread,
                    "offer_asset": {
                        "info": sellinfo,
                        "amount": str(amount)
                    },
                    "belief_price": belief_price
                }
            }        
        swap = MsgExecuteContract(
            sender=self.wallet.key.acc_address,
            contract=pool,
            execute_msg=swp,
            coins=Coins.from_str(str(amount)+''+sellinfo['native_token']['denom']),
        )
        sequence = self.wallet.sequence()
        tx = await self.wallet.create_and_sign_tx(
                            msgs=[swap], 
                            gas_prices=Coins(self.gas_prices),
                            gas_adjustment='1.4',
                            sequence = self.wallet.sequence()
                        )    
        result = self.broadcast_tx(tx)        
