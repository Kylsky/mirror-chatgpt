import os

import requests
from typing import Dict, List, Optional
from http.cookies import SimpleCookie
import json


class CloudflareSession:
    def __init__(self):
        self.session = requests.Session()
        self.user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

    def parse_set_cookie(self, set_cookie_str: str) -> Dict:
        """解析单个 Set-Cookie 字符串"""
        cookie = SimpleCookie()
        cookie.load(set_cookie_str)

        cookie_key = list(cookie.keys())[0]
        cookie_morsel = cookie[cookie_key]

        return {
            "name": cookie_key,
            "value": cookie_morsel.value,
            "domain": cookie_morsel["domain"] if "domain" in cookie_morsel else None,
            "path": cookie_morsel["path"] if "path" in cookie_morsel else None,
            "expires": cookie_morsel["expires"] if "expires" in cookie_morsel else None,
            "secure": "secure" in cookie_morsel,
            "httponly": "httponly" in cookie_morsel
        }

    def parse_all_cookies(self, headers: Dict[str, str]) -> List[Dict]:
        """解析响应头中的所有 Set-Cookie"""
        cookies = []
        set_cookie_headers = [
            v for k, v in headers.items()
            if k.lower() == 'set-cookie'
        ]

        for set_cookie in set_cookie_headers:
            try:
                cookie_data = self.parse_set_cookie(set_cookie)
                cookies.append(cookie_data)
            except Exception as e:
                print(f"Error parsing cookie: {str(e)}")

        return cookies

    def get_cloudflare_cookies(self, url: str, proxy: Optional[str] = None) -> Dict:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }

        proxies = None
        if proxy:
            proxies = {
                'http': proxy,
                'https': proxy
            }

        try:
            response = self.session.get(
                url,
                headers=headers,
                proxies=proxies,
                allow_redirects=True
            )

            # 解析 cookies
            cookies = self.parse_all_cookies(response.headers)

            result = {
                "exist_data_list": [{
                    "cookies": cookies,
                    "user_agent": self.user_agent,
                    "proxy_url": proxy,
                }],
                "need_update": {
                    "proxy_url_pool": [proxy] if proxy else [],
                    "user_agent_list": [self.user_agent]
                },
                "url": url
            }

            return result

        except Exception as e:
            print(f"Error getting Cloudflare cookies: {str(e)}")
            return None


def test_cookies():
    cf_session = CloudflareSession()

    # 使用代理（可选）
    proxy = os.getenv("PROXY", None)

    result = cf_session.get_cloudflare_cookies(
        url="https://chatgpt.com",
        proxy=proxy
    )

    if result:
        # 输出格式化的 JSON
        # print(json.dumps(result, indent=2))
        # 检查是否获取到关键的 CF cookies
        if result["exist_data_list"]:
            cf_cookies = [c for c in result["exist_data_list"][0]["cookies"]
                          if c["name"] in ["cf_clearance", "__cf_bm"]]
            if cf_cookies:
                print("\nFound Cloudflare cookies!")
                for cookie in cf_cookies:
                    print(f"  {cookie['name']}: {cookie['value']}")
        return json.dumps(result, indent=2)


# if __name__ == "__main__":
#     test_cookies()
