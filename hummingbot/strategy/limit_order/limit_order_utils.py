import string
from terra_sdk.core import Coin, Coins
import requests
import json
import os 

class LimitOrderUtils():
    # We use StrategyPyBase to inherit the structure. We also 
    # create a logger object before adding a constructor to the class. 

    def __init__(self, terra):
        self.is_ready = True
        self.terra = terra
    
    # MAX_NUM_TRADE_ATTEMPTS
    def number_of_trades_below_threshold(self, tradecount, threshold):
        print("number_of_trades_below_threshold", tradecount, threshold)
        return tradecount < int(threshold)

    # MINIMUM_WALLET_UST_BALANCE
    def balance_above_min_threshold(self, balance, currency, threshold):
        print("balance_above_min_threshold", balance, currency, threshold)
        if balance.get(currency) is not None:
            coinbal = balance[currency]
            print(coinbal.amount, "?", threshold)
            return coinbal.amount > int(threshold)            
        else:
            return False

    # BASE_TX_CURRENCY
    def check_base_currency(self, actualbase, desiredbase):
        print("check_base_currency", actualbase, desiredbase)
        return actualbase == desiredbase

    # DEFAULT_BASE_TX_SIZE
    def get_base_tx_size_from_balance(self, balance, currency, DEFAULT_BASE_TX_SIZE):
        print("get_base_tx_size_from_balance", balance, currency, DEFAULT_BASE_TX_SIZE)
        if balance.get(currency) is not None:
            amount = balance[currency].amount
            size = amount*float(DEFAULT_BASE_TX_SIZE)
        else:
            size = 0
        return int(size)

    # BASE_TX_CURRENCY

    def get_balance_from_wallet(self, balance, base):
        print("get_balance_from_wallet", balance, base)
        if balance.get(base) is not None:
            coinbalance = balance[base]
            return coinbalance
        else:
            return False

    # BASE_TX_CURRENCY
    def get_token_buy_limit_order_offset(self, pricing, BASE_LIMIT_PRICE, BASE_TX_CURRENCY):
        targettoken = self.parse_token_from_pair_pricing(pricing, BASE_TX_CURRENCY)
        price = (float(targettoken['price'])*10**6)
        offset = price-int(BASE_LIMIT_PRICE)
        withinthreshold = offset <= 0 if True else False
        return offset, price, withinthreshold, targettoken

    def get_token_sell_limit_order_offset(self, pricing, BASE_LIMIT_PRICE, BASE_TX_CURRENCY):
        targettoken = self.parse_token_from_pair_pricing(pricing, BASE_TX_CURRENCY)
        price = (float(targettoken['price'])*10**6)
        offset = price-int(BASE_LIMIT_PRICE)
        withinthreshold = offset >= 0 if True else False
        return offset, price, withinthreshold, targettoken

    def get_coin_buy_limit_order_offset(self, currency, BASE_LIMIT_PRICE):
        print("get_coin_buy_limit_order_offset", self.terra.oracle.exchange_rates(), currency, BASE_LIMIT_PRICE)
        if self.terra.oracle.exchange_rates().get(currency) is not None:
            rate = self.terra.oracle.exchange_rates()[currency]
            offset = rate.amount - int(BASE_LIMIT_PRICE)
            withinthreshold = offset <= 0 if True else False
        else: 
            offset = 0
            rate = 0
            withinthreshold = False
        return offset, rate, withinthreshold

    def get_coin_sell_limit_order_offset(self, currency, BASE_LIMIT_PRICE):
        print("get_coin_sell_limit_order_offset", self.terra.oracle.exchange_rates(), currency, BASE_LIMIT_PRICE)
        if self.terra.oracle.exchange_rates().get(currency) is not None:
            rate = self.terra.oracle.exchange_rates()[currency]
            offset = rate.amount - int(BASE_LIMIT_PRICE)
            withinthreshold = offset >= 0 if True else False
        else: 
            offset = 0
            rate = 0
            withinthreshold = False
        return offset, rate, withinthreshold


    def coin_to_denom(self, coin):
        target = ''
        cwd = os.getcwd()
        coin_to_denom = json.load(open(cwd+'/hummingbot/strategy/limit_order/coin_to_denom.json'))

        for attribute, value in coin_to_denom.items():
            # print(attribute, value) # example usage       
            if coin == attribute:                           # Get coin denomination from Trading Pair name
                target = value
        return target

    def get_tokens(self):
        # Luna-USST
        # https://api.terraswap.io/tokens
        tokens = requests.get('https://api.terraswap.io/tokens').json()
        # print("get_tokens")
        return tokens

    def get_pair_txs(self, pair_address:string):
        txns = requests.get('https://api.terraswap.io/dashboard/txs?page=1&pair='+pair_address).json()
        print("get_pair_txs")
        return txns        

    def get_pair_pricing(self, pair_address):
        pricing = requests.get('https://api.terraswap.io/dashboard/pairs/'+pair_address).json()
        return pricing

    def parse_token_from_pair_pricing(self, pricing, symbol):
        token = []
        if pricing.get("token0") is not None:
            if pricing["token0"]["symbol"] == symbol:
                token = pricing["token0"]
        if pricing.get("token1") is not None:
            if pricing["token1"]["symbol"] == symbol:
                token = pricing["token1"]                                              
        return token

    def find_token_pair_contract_from_tokens(self, tokens, contract_addr):
        target_pair = []
        print("find_token_pair_contract_from_tokens")
        print(contract_addr)   
        for s in range(len(tokens)):
            token = tokens[s]
            if 'contract_addr' in token:
                if token['contract_addr'] == contract_addr:
                    target_token = token
        return target_pair

    def find_token_pair_contract_from_pairs(self, pairs, market):
        target_pair = []
        print("find_token_pair_contract_from_pairs")
        print(market)
        print(len(pairs))
        for s in range(len(pairs)):
            pair = pairs[s]
            if 'pairAddress' in pair:
                if 'pairAlias' in pair:
                    if pair["pairAlias"] == market:
                        target_pair = pair
        return target_pair

    def find_asset_info_from_pair(self, pairAddress, asset_info_pairs):
        target_asset_infos = []
        print("find_asset_info_from_pair")
        print(pairAddress)
        print(len(asset_info_pairs))
        for s in range(len(asset_info_pairs)):
            p = asset_info_pairs[s]
            if 'contract_addr' in p:
                if p["contract_addr"] == pairAddress:
                        target_asset_infos = p
        return target_asset_infos

    def parse_native_token_from_token_pair_asset(self, pair):
        target = []
        for s in range(len(pair['asset_infos'])):
            asset_info = pair['asset_infos'][s]
            if 'native_token' in asset_info:
                target = asset_info['native_token']
        return target


