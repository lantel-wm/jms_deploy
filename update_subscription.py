import argparse
import base64
import json
import os
import subprocess
from dataclasses import dataclass
from typing import Dict, List

import requests


@dataclass
class ServerInfo:
    protocol: str  # shadowsocks | vmess
    tag: str
    address: str
    port: int

    # vmess only
    uuid: str = ""
    alterId: int = 0

    # shadowsocks only
    method: str = ""
    password: str = ""


class SubParser:
    def __init__(self, url):
        self.url = url

    def parse(self) -> List[str] | None:
        self.subscription = self.fetch_subscription()
        decoded_urls = self.decode_subscription()
        server_info_list = self.decode_server_info(decoded_urls)
        return server_info_list

    def fetch_subscription(self) -> str | None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
        }
        try:
            response = requests.get(self.url, headers=headers)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Request subscription URL error: {e}")
            return None

    def decode_subscription(self) -> List[str] | None:
        try:
            decoded_urls = base64.b64decode(self.subscription).decode("utf-8")
            decoded_urls = decoded_urls.split("\n")
            return decoded_urls
        except Exception as e:
            print(f"Decode failed: {e}")
            return None

    def decode_server_info(self, decoded_urls: List[str]) -> List[ServerInfo]:
        server_info_list = []
        for url in decoded_urls:
            try:
                if url.startswith("vmess://"):
                    data = self.decode_vmess(url)
                    server_info_list.append(
                        ServerInfo(
                            protocol="vmess",
                            tag=data["ps"],
                            address=data["add"],
                            port=int(data["port"]),
                            uuid=data["id"],
                            alterId=data["aid"],
                        )
                    )
                elif url.startswith("ss://"):
                    data = self.decode_shadowsocks(url)
                    server_info_list.append(
                        ServerInfo(
                            protocol="shadowsocks",
                            tag=data["tag"],
                            address=data["address"],
                            port=int(data["port"]),
                            method=data["method"],
                            password=data["password"],
                        )
                    )
            except Exception as e:
                print(f"Decode server info failed: {e}")

        return server_info_list

    def pad(self, s: str) -> str:
        padding = len(s) % 4
        if padding != 0:
            s += "=" * (4 - padding)
        return s

    def decode_vmess(self, vmess_url: str) -> Dict:
        vmess_data = self.pad(vmess_url[8:])
        data = base64.b64decode(vmess_data).decode("utf-8")
        return json.loads(data)

    def decode_shadowsocks(self, ss_url: str) -> Dict:
        ss_data = self.pad(ss_url[5:].split("#")[0])
        data = base64.b64decode(ss_data).decode("utf-8")

        method_password, host_port = data.split("@")
        method, password = method_password.split(":")
        host, port = host_port.split(":")

        tag = ss_url.split("#")[1]

        return {
            "tag": tag,
            "method": method,
            "password": password,
            "address": host,
            "port": port,
        }


class V2rayConfigDumper:
    def __init__(self, config_template_path: str, config_dump_path: str):
        self.config_dump_path = config_dump_path
        with open(config_template_path) as f:
            self.config = json.load(f)

    def dump_config(self):
        with open(self.config_dump_path, "w") as f:
            json.dump(self.config, f, indent=4)

    def update_config(self, server_info_list: List[ServerInfo]):
        vmess_outbound_template = None
        ss_outbound_template = None
        for outbound in self.config["outbounds"]:
            if outbound["protocol"] == "vmess":
                vmess_outbound_template = outbound.copy()
            elif outbound["protocol"] == "shadowsocks":
                ss_outbound_template = outbound.copy()

        assert (
            vmess_outbound_template is not None
        ), "Make sure default_config.json has vmess outbound"

        assert (
            ss_outbound_template is not None
        ), "Make sure default_config.json has shadowsocks outbound"

        self.update_outbounds(
            vmess_outbound_template, ss_outbound_template, server_info_list
        )

        self.update_routing(server_info_list)

    def update_outbounds(
        self,
        vmess_outbound_template: Dict,
        ss_outbound_template: Dict,
        server_info_list: List[ServerInfo],
    ):
        outbounds = []
        for info in server_info_list:
            assert info.protocol in [
                "vmess",
                "shadowsocks",
            ], f"Unsupported protocol: {info.protocol}"

            if info.protocol == "vmess":
                outbound = vmess_outbound_template.copy()
                outbound["tag"] = info.tag
                outbound["settings"]["vnext"][0]["address"] = info.address
                outbound["settings"]["vnext"][0]["port"] = info.port
                outbound["settings"]["vnext"][0]["users"][0]["id"] = info.uuid
                outbound["settings"]["vnext"][0]["users"][0]["alterId"] = info.alterId
            elif info.protocol == "shadowsocks":
                outbound = ss_outbound_template.copy()
                outbound["tag"] = info.tag
                outbound["settings"]["servers"][0]["address"] = info.address
                outbound["settings"]["servers"][0]["port"] = info.port
                outbound["settings"]["servers"][0]["password"] = info.password
                outbound["settings"]["servers"][0]["method"] = info.method

            outbounds.append(outbound)

        self.config["outbounds"] = outbounds

    def update_routing(self, server_info_list: List[ServerInfo]):
        selector = [info.tag for info in server_info_list]
        self.config["routing"]["balancers"][0]["selector"] = selector


class V2rayRestarter:
    def __init__(
        self,
        subscription_url: str,
        config_path: str,
        config_template_path: str,
    ):
        self.url = subscription_url
        self.config_path = config_path
        self.config_template_path = config_template_path
        self.parser = SubParser(subscription_url)
        self.dumper = V2rayConfigDumper(config_template_path, config_path)

    def restart(self):
        server_info_list = self.parser.parse()
        self.dumper.update_config(server_info_list)
        self.dumper.dump_config()

        subprocess.run(["systemctl", "restart", "v2ray"], check=True)


if __name__ == "__main__":
    os.environ["http_proxy"] = ""
    os.environ["https_proxy"] = ""
    os.environ["HTTP_PROXY"] = ""
    os.environ["HTTPS_PROXY"] = ""

    parser = argparse.ArgumentParser()
    parser.add_argument("--url", type=str, required=True, help="Subscription url")
    parser.add_argument("--config-path", type=str, required=True, help="Config path")
    parser.add_argument(
        "--config-template-path", type=str, required=True, help="Config template path"
    )
    args = parser.parse_args()

    restarter = V2rayRestarter(args.url, args.config_path, args.config_template_path)
    restarter.restart()
