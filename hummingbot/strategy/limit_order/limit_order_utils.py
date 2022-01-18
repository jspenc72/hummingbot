from terra_sdk.core import Coin, Coins
import requests

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
        if balance[currency]:
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
        if balance[currency]:    
            amount = balance[currency].amount
            size = amount*float(DEFAULT_BASE_TX_SIZE)
        else:
            size = 0

        return int(size)

    # BASE_TX_CURRENCY
    def get_limit_order_offset(self, currency, BASE_LIMIT_PRICE, EXPOSURE_PERCENTAGE):
        rate = self.terra.oracle.exchange_rates()[currency]
        print(rate)
        print("get_limit_order_offset", rate, BASE_LIMIT_PRICE, EXPOSURE_PERCENTAGE)
        offsetpercent = rate.amount / int(BASE_LIMIT_PRICE)
        withinthreshold = offsetpercent <= float(EXPOSURE_PERCENTAGE)
        return offsetpercent, withinthreshold

    def get_txs_for_pair(self, pair):
        # Luna-USST
        # https://api.terraswap.io/dashboard/txs?page=1&pair=terra1tndcaqxkpc5ce9qee5ggqf430mr2z3pefe5wj6
        print("get_txs_for_pair")

    def get_tokens(self):
        # Luna-USST
        # https://api.terraswap.io/tokens
        tokens = requests.get('https://assets.terra.money/ibc/tokens.json').json()
        print("get_tokens")
        return tokens