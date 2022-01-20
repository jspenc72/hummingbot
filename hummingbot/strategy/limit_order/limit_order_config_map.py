from hummingbot.client.config.config_var import ConfigVar

# Returns a market prompt that incorporates the connector value set by the user
def market_prompt() -> str:
    connector = limit_order_config_map.get("connector").value
    return f'Enter the token trading pair on {connector} >>> '
 
# List of parameters defined by the strategy
limit_order_config_map ={
    "strategy":
        ConfigVar(key="strategy",
                  prompt="",
                  default="limit_order",
    ),
    "connector":
        ConfigVar(key="connector",
                  prompt="Enter the name of the exchange >>> ",
                  prompt_on_new=True,
    ),
    "TARGET_PAIR": ConfigVar(
        key="TARGET_PAIR",
        prompt=market_prompt,
        prompt_on_new=True,
    ),
    "OFFER_ASSET": ConfigVar(
        key="OFFER_ASSET",
        prompt="Enter the symbol of the asset you wish to offer in buy orders >>> ",
        prompt_on_new=True,
    ),    
    "MAX_NUM_TRADE_ATTEMPTS":
        ConfigVar(key="MAX_NUM_TRADE_ATTEMPTS", 
                  prompt="Enter the value of MAX_NUM_TRADE_ATTEMPTS >>> ",
                  default="2",
                  prompt_on_new=True,
    ),
    "MINIMUM_WALLET_UST_BALANCE":
        ConfigVar(key="MINIMUM_WALLET_UST_BALANCE", 
                  prompt="Enter the value of MINIMUM_WALLET_UST_BALANCE (Enter 5000000 for $5.00) >>> ",
                  default="5000000"
    ),
    "ORDER_TYPE":
        ConfigVar(key="ORDER_TYPE", 
                  prompt="Enter the value of ORDER_TYPE (BUY | SELL)>>> ",
                  default="BUY",
                  prompt_on_new=True,
    ),
    "BASE_LIMIT_PRICE":
        ConfigVar(key="BASE_LIMIT_PRICE", 
                  prompt="Enter the value of BASE_LIMIT_PRICE (70000000uluna) would be entered as 70000000 >>> ",
                  default="70000000",
                  prompt_on_new=True,
    ),
    "BASE_TX_CURRENCY":
        ConfigVar(key="BASE_TX_CURRENCY", 
                  prompt="Enter the symbol to use for fees and gas (UST | Luna | bLuna)>>> ",
                  default="UST",
                  prompt_on_new=True,
    ),
    "DEFAULT_BASE_TX_SIZE_PERCENTAGE_OF_BAL":
        ConfigVar(key="DEFAULT_BASE_TX_SIZE_PERCENTAGE_OF_BAL", 
                  prompt="Enter the value of DEFAULT_BASE_TX_SIZE_PERCENTAGE_OF_BAL (0.8 * walletbalance)>>> ",
                  default="0.8",
                  prompt_on_new=True,
    ),
    "DEFAULT_MAX_SPREAD":
        ConfigVar(key="DEFAULT_MAX_SPREAD", 
                  prompt="Enter the value of DEFAULT_MAX_SPREAD >>> ",
                  default="0.005"
    ),
    "USE_MAX_TRANSACTION_SIZE":
        ConfigVar(key="USE_MAX_TRANSACTION_SIZE", 
                  prompt="Enter the value of USE_MAX_TRANSACTION_SIZE >>> ",
                  default="True",
                  prompt_on_new=True,
    )
}