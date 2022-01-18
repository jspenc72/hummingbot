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
    def get_token_buy_limit_order_offset(self, pricing, BASE_LIMIT_PRICE):
        price = (float(pricing['token0']['price'])*10**6)
        offset = price-int(BASE_LIMIT_PRICE)
        withinthreshold = offset <= 0 if True else False
        return offset, price, withinthreshold

    def get_token_sell_limit_order_offset(self, pricing, BASE_LIMIT_PRICE):
        price = (float(pricing['token0']['price'])*10**6)
        offset = price-int(BASE_LIMIT_PRICE)
        withinthreshold = offset >= 0 if True else False
        return offset, price, withinthreshold        

    def get_coin_buy_limit_order_offset(self, currency, BASE_LIMIT_PRICE):
        print("get_coin_buy_limit_order_offset", self.terra.oracle.exchange_rates(), currency, BASE_LIMIT_PRICE)
        if self.terra.oracle.exchange_rates().get(currency) is not None:
            rate = self.terra.oracle.exchange_rates()[currency]
            print(rate)
            offset = rate.amount - int(BASE_LIMIT_PRICE)
            withinthreshold = offset <= 0 if True else False
        else: 
            offset = 0
            withinthreshold = False
        return offset, withinthreshold

    def get_coin_sell_limit_order_offset(self, currency, BASE_LIMIT_PRICE):
        if self.terra.oracle.exchange_rates().get(currency) is not None:
            rate = self.terra.oracle.exchange_rates()[currency]
            print(rate)
            print("get_limit_order_offset", rate, BASE_LIMIT_PRICE)
            offset = rate.amount - int(BASE_LIMIT_PRICE)
            withinthreshold = offset >= 0 if True else False
        else: 
            offset = 0
            withinthreshold = False
        return offset, withinthreshold


    def coin_to_denom(self, coin):
        target = ''
        cwd = os.getcwd()
        coin_to_denom = json.load(open(cwd+'/hummingbot/strategy/limit_order/coin_to_denom.json'))

        for attribute, value in coin_to_denom.items():
            # print(attribute, value) # example usage       
            if coin == attribute:                           # Get coin denomination from Trading Pair name
                print("found: "+attribute, 'with symbol '+ value)
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
        print("get_pair_pricing")
        return pricing

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