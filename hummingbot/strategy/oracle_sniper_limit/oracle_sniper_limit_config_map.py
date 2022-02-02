from hummingbot.client import settings
from hummingbot.client.config.config_helpers import parse_cvar_value
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_validators import (
    validate_market_trading_pair,
    validate_connector,
    validate_decimal,
    validate_bool
)
from hummingbot.client.settings import (
    required_exchanges,
    requried_connector_trading_pairs,
    AllConnectorSettings,
)

from decimal import Decimal


def exchange_on_validated(value: str) -> None:
    required_exchanges.append(value)


def market_1_validator(value: str) -> None:
    exchange = oracle_sniper_limit_config_map["connector_1"].value
    return validate_market_trading_pair(exchange, value)


def market_1_on_validated(value: str) -> None:
    requried_connector_trading_pairs[oracle_sniper_limit_config_map["connector_1"].value] = [value]


def market_2_validator(value: str) -> None:
    exchange = oracle_sniper_limit_config_map["connector_2"].value
    return validate_market_trading_pair(exchange, value)


def market_2_on_validated(value: str) -> None:
    requried_connector_trading_pairs[oracle_sniper_limit_config_map["connector_2"].value] = [value]


def market_1_prompt() -> str:
    connector = oracle_sniper_limit_config_map.get("connector_1").value
    example = AllConnectorSettings.get_example_pairs().get(connector)
    return "Enter the token trading pair you would like to trade on %s%s >>> " \
           % (connector, f" (e.g. {example})" if example else "")


def market_2_prompt() -> str:
    connector = oracle_sniper_limit_config_map.get("connector_2").value
    example = AllConnectorSettings.get_example_pairs().get(connector)
    return "Enter the token trading pair you would like to use for oracle pricing on %s%s >>> " \
           % (connector, f" (e.g. {example})" if example else "")


def order_amount_prompt() -> str:
    trading_pair = oracle_sniper_limit_config_map["market_1"].value
    base_asset, quote_asset = trading_pair.split("-")
    return f"What is the amount of {base_asset} per order? >>> "


def update_oracle_settings(value: str):
    c_map = oracle_sniper_limit_config_map
    if not (c_map["use_oracle_conversion_rate"].value is not None and
            c_map["market_1"].value is not None and
            c_map["market_2"].value is not None):
        return
    use_oracle = parse_cvar_value(c_map["use_oracle_conversion_rate"], c_map["use_oracle_conversion_rate"].value)
    first_base, first_quote = c_map["market_1"].value.split("-")
    second_base, second_quote = c_map["market_2"].value.split("-")
    if use_oracle and (first_base != second_base or first_quote != second_quote):
        settings.required_rate_oracle = True
        settings.rate_oracle_pairs = []
        if first_base != second_base:
            settings.rate_oracle_pairs.append(f"{second_base}-{first_base}")
        if first_quote != second_quote:
            settings.rate_oracle_pairs.append(f"{second_quote}-{first_quote}")
    else:
        settings.required_rate_oracle = False
        settings.rate_oracle_pairs = []

def offer_coin_prompt() -> str:
    market = oracle_sniper_limit_config_map.get("TARGET_PAIR").value
    base, quote = market.split("-")
    return f'Which coin would you like to offer in your trades {base} or {quote} >>> '
 
def default_offer_coin() -> str:
    market = oracle_sniper_limit_config_map.get("TARGET_PAIR").value
    base, quote = market.split("-")
    return base
  

# List of parameters defined by the strategy
oracle_sniper_limit_config_map ={
    "strategy":
        ConfigVar(key="strategy",
                  prompt="",
                  default="oracle_sniper_limit",
    ),
    "connector_1": ConfigVar(
        key="connector_1",
        prompt="Enter the name of the oracle exchange connector (Exchange/AMM) >>> ",
        default="terraswap",
        prompt_on_new=True,
        validator=validate_connector,
        on_validated=exchange_on_validated),
    "TARGET_PAIR": ConfigVar(
        key="TARGET_PAIR",
        prompt=market_1_prompt,
        prompt_on_new=True,
        validator=market_1_validator,
        on_validated=market_1_on_validated,
    ), 
    "OFFER_ASSET": ConfigVar(
        key="OFFER_ASSET",
        prompt=offer_coin_prompt,
        prompt_on_new=True,
        default=default_offer_coin
    ),              
    "connector_2": ConfigVar(
        key="connector_2",
        prompt="Enter your second spot connector (Exchange/AMM) >>> ",
        prompt_on_new=True,
        validator=validate_connector,
        on_validated=exchange_on_validated),

    "ORACLE_PAIR": ConfigVar(
        key="ORACLE_PAIR",
        prompt=market_2_prompt,
        prompt_on_new=True,
        validator=market_2_validator,
        on_validated=market_2_on_validated),
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