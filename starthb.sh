#!/bin/bash

docker run --env SECRET_TERRA_MNEMONIC="lots of things here" -it \
    --network host \
    --mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
    --mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
    --mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_data,destination=/data/" \
    --mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_certs,destination=/certs/" \
    --mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_scripts,destination=/scripts/" \
    --mount "type=bind,source=$(pwd)/hummingbot/strategy/limit_order,destination=/home/hummingbot/hummingbot/strategy/limit_order/" \
    --mount "type=bind,source=$(pwd)/hummingbot/templates/,destination=/home/hummingbot/hummingbot/templates/" \
    --mount "type=bind,source=$(pwd)/hummingbot/connector/connector/terraswap,destination=/home/hummingbot/hummingbot/connector/connector/terraswap/" \
    jspenc72/hummingbot:terraswap