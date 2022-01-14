from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.settings import required_exchanges

CENTRALIZED = False
EXAMPLE_PAIR = "LUNA-UST"
DEFAULT_FEES = [0., 0.]


KEYS = {
    "terraswap_wallet_address":
        ConfigVar(key="terraswap_wallet_address",
                  prompt="Enter your Terra wallet address >>> ",
                  required_if=lambda: "terraswap" in required_exchanges,
                  is_secure=True,
                  is_connect_key=True),
    "terraswap_wallet_seeds":
        ConfigVar(key="terraswap_wallet_seeds",
                  prompt="Enter your Terra wallet seeds >>> ",
                  required_if=lambda: "terraswap" in required_exchanges,
                  is_secure=True,
                  is_connect_key=True),
}
