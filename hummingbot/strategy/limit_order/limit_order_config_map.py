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
    "MAX_NUM_TRADE_ATTEMPTS":
        ConfigVar(key="connector", 
                  prompt="Enter the value of MAX_NUM_TRADE_ATTEMPTS >>> ",
                  default="MAX_NUM_TRADE_ATTEMPTS"
    ),
    "MINIMUM_WALLET_UST_BALANCE":
        ConfigVar(key="connector", 
                  prompt="Enter the value of MINIMUM_WALLET_UST_BALANCE >>> ",
                  default="MINIMUM_WALLET_UST_BALANCE"
    ),
    "ORDER_TYPE":
        ConfigVar(key="connector", 
                  prompt="Enter the value of ORDER_TYPE >>> ",
                  default="ORDER_TYPE"
    ),
    "BASE_LIMIT_PRICE":
        ConfigVar(key="connector", 
                  prompt="Enter the value of BASE_LIMIT_PRICE >>> ",
                  default="BASE_LIMIT_PRICE"
    ),
    "BASE_TX_CURRENCY":
        ConfigVar(key="connector", 
                  prompt="Enter the value of BASE_TX_CURRENCY >>> ",
                  default="BASE_TX_CURRENCY"
    ),
    "DEFAULT_BASE_TX_SIZE":
        ConfigVar(key="connector", 
                  prompt="Enter the value of DEFAULT_BASE_TX_SIZE >>> ",
                  default="DEFAULT_BASE_TX_SIZE"
    ),
    "DEFAULT_MAX_SPREAD":
        ConfigVar(key="connector", 
                  prompt="Enter the value of DEFAULT_MAX_SPREAD >>> ",
                  default="DEFAULT_MAX_SPREAD"
    ),
    "USE_MAX_TRANSACTION_SIZE":
        ConfigVar(key="connector", 
                  prompt="Enter the value of USE_MAX_TRANSACTION_SIZE >>> ",
                  default="USE_MAX_TRANSACTION_SIZE"
    ),
    "EXPOSURE_PERCENTAGE":
        ConfigVar(key="connector", 
                  prompt="Enter the value of EXPOSURE_PERCENTAGE >>> ",
                  default="EXPOSURE_PERCENTAGE"
    ),
    "TARGET_PAIR": ConfigVar(
        key="TARGET_PAIR",
        prompt=market_prompt,
        prompt_on_new=True,
    ),
}