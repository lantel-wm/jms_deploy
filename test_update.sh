#!/bin/bash

SUBSCRIPTION_URL="your-subscription-url"

/usr/bin/python3 ./update_subscription.py \
--url "$SUBSCRIPTION_URL" \
--config-path /etc/v2ray/config.json \
--config-template-path ./config_template.json