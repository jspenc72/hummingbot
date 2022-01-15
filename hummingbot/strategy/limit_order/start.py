#!/usr/bin/env python
from lib2to3.pgen2 import token
from terra_sdk.client.lcd import LCDClient
import requests
import json
import os 

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.limit_order import LimitOrder
from hummingbot.strategy.limit_order.limit_order_config_map import limit_order_config_map as c_map

def start(self):
    try:
        connector = c_map.get("connector").value.lower()
        market = c_map.get("market").value

        self._initialize_markets([(connector, [market])])
        base, quote = market.split("-")
        market_info = MarketTradingPairTuple(self.markets[connector], market, base, quote)
        self.market_trading_pair_tuples = [market_info]
        terra = LCDClient(chain_id="columbus-4", url="https://lcd.terra.dev")
        # Opening JSON file
        cwd = os.getcwd() 
        cw20_path = cwd+'/hummingbot/strategy/limit_order/cw20.json'
        ibc_path = cwd+'/hummingbot/strategy/limit_order/ibc.json'
        fcw20pairs_path = cwd+'/hummingbot/strategy/limit_order/pairs.dex.json'
        coin_to_denom_path = cwd+'/hummingbot/strategy/limit_order/coin_to_denom.json'
        fcw20 = open(cw20_path)
        fibc = open(ibc_path)
        fcw20pairs = open(fcw20pairs_path)
        fcoin_to_denom = open(coin_to_denom_path)
        terra_swap_coins = ["Luna","UST","AUT","CAT","CHT","CNT","DKT","EUT","GBT","HKT","IDT","INT","JPT","KRT","MNT","PHT","SDT","SET","SGT","THT"]
        terra_swap_tokens = ["SCRT","ANC","bLuna","MIR","mAAPL","mABNB","mAMC","mAMD","mAMZN","mBABA","mBTC","mCOIN","mDOT","mETH","mFB","mGLXY","mGME","mGOOGL","mGS","mIAU","mMSFT","mNFLX","mQQQ","mSLV","mSPY","mSQ","mTSLA","mTWTR","mUSO","mVIXY","MINE","bPsiDP-24m","Psi","LOTA","SPEC","STT","TWD","MIAW","VKR","ORION","KUJI","wewstETH","wsstSOL","LunaX","ORNE","TLAND","LUNI","PLY","ASTRO","XRUNE","SITY"]

        # returns JSON object as
        # a dictionary
        cw20_data = json.load(fcw20)
        ibc_data = json.load(fibc)
        cw20pairs = json.load(fcw20pairs)
        coin_to_denom = json.load(fcoin_to_denom)

        # Find offer target denom
        token_target = ''
        offer_target = ''
        ask_target = ''
        for attribute, value in coin_to_denom.items():
            # print(attribute, value) # example usage       
            if base == attribute:                           # Get coin denomination from Trading Pair name
                print("found: "+attribute, 'with symbol '+ value)
                offer_target = value
        # Find ask target denom
        for attribute, value in coin_to_denom.items():
            if quote == attribute:                           # Get coin denomination from Trading Pair name
                print("found: "+attribute, 'with symbol '+ value)
                ask_target = value

        if offer_target != '' and ask_target != '':
            print("found trading pair: ", offer_target, ask_target)
# COIN-COIN
        else:
            print("base trading pair "+market+". "+ base +"-"+ quote +" not found searching for matching Terra ERC20 tokens")
            
            if ask_target == '':
# COIN-SOME_possible_TOKEN
                # Find target token
                for attribute, value in cw20_data['mainnet'].items():
                    if quote == value['symbol']:
                        # is candidate, need to search
                        # print(attribute, value) # example usage
                        print("found: " + quote, "with token address: "+attribute)
                        token_target = attribute
                        ask_target = token_target
            elif offer_target == '':
# SOME_possible_TOKEN-Luna
                print("market is "+market+" token to coin, only option is token to Luna!")
            else: 
                print("unknown trade type, cannot find matching pair")
        print("final trading pair: ", offer_target +" > " + ask_target)
        self.strategy = LimitOrder(market_info, 
                                    terra_client=terra,
                                    offer_target= offer_target,
                                    ask_target=ask_target,
                                    token_target=token_target)

    except Exception as e:
        self._notify(str(e))
        self.logger().error("Unknown error during initialization.", exc_info=True)



        # cw20tokens = requests.get('https://assets.terra.money/cw20/tokens.json').json()
        # ibctokens = requests.get('https://assets.terra.money/ibc/tokens.json').json()
        # cw20pairs = requests.get('https://assets.terra.money/cw20/pairs.dex.json').json()
        # terracontracts = requests.get('https://assets.terra.money/contracts.json').json()
        # ibctokens = requests.get('https://assets.terra.money/chains.json').json()
