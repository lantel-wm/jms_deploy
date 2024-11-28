# JMS Deploy

A light weight tool for updating v2ray config from JMS subscription.

## Usage

Install v2ray: 

```bash
sudo apt install v2ray
```

Check v2ray status using systemd:
```bash
sudo systemctl status v2ray
```

Test update script:
```bash
#!/bin/bash

SUBSCRIPTION_URL="your-subscription-url"

/usr/bin/python3 ./update_subscription.py \
--url "$SUBSCRIPTION_URL" \
--config-path /etc/v2ray/config.json \
--config-template-path ./config_template.json
```

Change the subscription url to your own subscription url, and run the script. (Maybe need to add `sudo` to the script)

Check the status of v2ray again, if v2ray has been restarted, it means the script works.

# Automatic update

Add the script to crontab:

```bash
sudo crontab -e
```

Add the following line to the crontab file:

```bash
0 * * * * /usr/bin/python3 /path/to/update_subscription.py --url "your-subscription-url" --config-path /etc/v2ray/config.json --config-template-path ./config_template.json
```

The script will be executed every hour.