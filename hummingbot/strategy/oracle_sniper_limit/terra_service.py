import asyncio
import requests
import string,os,time,sys,json
from decimal import Decimal

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
    chain_id = 'columbus-5'
    chain_url = 'https://lcd.terra.dev'
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
                print("Something Went Wrong. Hummingbot shutting down now...")
                time.sleep(3)
                sys.exit("Something Went Wrong!")        
            self.load_files()
            self.pull_api_info()

    async def request_updated_wallet_balance(self):
        print("checking available balance...")
        res = self.request_updated_gas_prices()
        async with AsyncLCDClient(chain_id="columbus-5", url="https://lcd.terra.dev", gas_prices=Coins(res), gas_adjustment="1.4") as terra:
            self.terra = terra                
            self.balance = await self.terra.bank.balance(self.mk.acc_address)
            return self.balance
    
    async def contract_query(self, pool):
        res = self.request_updated_gas_prices()
        async with AsyncLCDClient(chain_id="columbus-5", url="https://lcd.terra.dev", gas_prices=Coins(res), gas_adjustment="1.4") as terra:
            self.terra = terra           
            assets = await self.terra.wasm.contract_query(pool, { "pool": {} })
            return assets

    # Utils
    def balance_above_min_threshold(self, balance, currency, threshold):
        print("balance_above_min_threshold", balance, currency, threshold)
        if balance.get(currency) is not None:
            coinbal = balance[currency]
            return coinbal.amount > int(threshold)            
        else:
            return False

    def coin_to_denom(self, coin):
        target = ''
        cwd = os.getcwd()
        coin_to_denom = json.load(open(cwd+'/hummingbot/strategy/limit_order/coin_to_denom.json'))

        for attribute, value in coin_to_denom.items():
            # print(attribute, value) # example usage       
            if coin == attribute:                           # Get coin denomination from Trading Pair name
                target = value
        return target

    def get_balance_from_wallet(self, balance, base):
        print("get_balance_from_wallet", balance, base)
        if balance.get(base) is not None:
            coinbalance = balance[base]
            return coinbalance
        else:
            return False

    # Public api.terraswap.io Library Methods
    def request_updated_gas_prices(self):
        self.gas_prices = requests.get("https://fcd.terra.dev/v1/txs/gas_prices").json()

    def pull_api_info(self):
        self.request_cw20_tokens()
        self.request_cw20_pairs()
        self.request_asset_info_pairs()

    def get_tokens(self):
        return self.request_cw20_tokens()

    def get_pair_txs(self, pair_address:string):
        txns = requests.get('https://api.terraswap.io/dashboard/txs?page=1&pair='+pair_address).json()
        return txns        

    def get_pair_pricing(self, pair_address):
        pricing = requests.get('https://api.terraswap.io/dashboard/pairs/'+pair_address).json()
        return pricing

    def get_token_pricing(self, pair_address, symbol):
        pricing = requests.get('https://api.terraswap.io/dashboard/pairs/'+pair_address).json()
        token = []
        if pricing.get("token0") is not None:
            if pricing["token0"]["symbol"] == symbol:
                token = pricing["token0"]
        if pricing.get("token1") is not None:
            if pricing["token1"]["symbol"] == symbol:
                token = pricing["token1"]                                              
        return token


    def get_currency_amount_from_wallet_balance(self, balance, currency):
        print("get_currency_amount_from_wallet_balance", balance, currency)
        amount = 0
        if balance.get(currency) is not None:
            amount = balance[currency].amount
        else:
            amount = 0
        return amount

    def get_base_tx_size_from_balance(self, balance, currency, DEFAULT_BASE_TX_SIZE):
        print("get_base_tx_size_from_balance", balance, currency, DEFAULT_BASE_TX_SIZE)
        if balance.get(currency) is not None:
            amount = balance[currency].amount
            size = amount*float(DEFAULT_BASE_TX_SIZE)
        else:
            size = 0
        return int(size)

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
        res = self.request_updated_gas_prices()
        async with AsyncLCDClient(chain_id="columbus-5", url="https://lcd.terra.dev", gas_prices=Coins(res), gas_adjustment="1.4") as terra:
            self.terra = terra          
    
    async def send(self, recipient_wallet_addr, coins):
        wallet = self.terra.wallet(self.mk)
        account_number = await wallet.account_number()
        tx = await wallet.create_and_sign_tx(
            msgs=[MsgSend(wallet.key.acc_address, recipient_wallet_addr, coins)]
        )
        result = self.terra.tx.broadcast(tx)


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
        result = self.terra.tx.broadcast(tx)


    def token_swap(self, pool, amount, sellinfo, belief_price, max_spread=0.5):
        # Get reference to wallet 
        res = self.request_updated_gas_prices()
        terra = LCDClient(chain_id="columbus-5", url="https://lcd.terra.dev", gas_prices=Coins(res), gas_adjustment="1.4")
            
        wallet = terra.wallet(self.mk)
        seq = wallet.sequence()
        account_number = wallet.account_number()

        gp = self.gas_prices.get(sellinfo['native_token']['denom'])+sellinfo['native_token']['denom']
        
        # print("account_number")
        # print(account_number)
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
        print(swp)  
        swap = MsgExecuteContract(
            sender=wallet.key.acc_address,
            contract=pool,
            execute_msg=swp,
            coins=Coins.from_str(str(amount)+''+sellinfo['native_token']['denom']),
        )
        print(swap)        
        print('dynamic gas: ',gp)
        tx = wallet.create_and_sign_tx(
                            msgs=[swap], 
                            gas_prices=gp,
                            gas_adjustment='1.4',
                            sequence = seq
                        )
        print(tx)
        return terra.tx.broadcast(tx)