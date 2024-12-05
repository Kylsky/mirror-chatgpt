import hashlib
import os

import requests

from entity.share import Share
from utils.redis_util import RedisUtils


def refresh_to_access(refresh_token: str):
    if os.getenv('PROXY', '') != '':
        proxy_cfg = {
            'http': os.getenv('PROXY', '').split(",")[0],
            'https': os.getenv('PROXY', '').split(",")[0]
        }
        requests.Session().proxies.update(proxy_cfg)

    headers = {
        "Content-Type": "application/json",
    }
    req_body = {
        "refresh_token": refresh_token,
        "redirect_uri": "com.openai.chat://auth0.openai.com/ios/com.openai.chat/callback",
        "grant_type": "refresh_token",
        "client_id": "pdlLIX2Y72MIl2rhLhTE9VV9bN905kBh"
    }
    resp = requests.post(
        url="https://auth0.openai.com/oauth/token",
        headers=headers,
        json=req_body
    )
    if resp.status_code == 200:
        return resp.json()['access_token']
    else:
        return None


def access_to_share(share_info: Share):
    share_token = generate_short_token(share_info.access_token, share_info.user_name)
    return share_token


def generate_short_token(access_token, username):
    # 将用户名和长token拼接
    combined_string = access_token + username
    # 使用SHA-256哈希算法生成固定长度的短token
    short_token = "fk-" + hashlib.sha256(combined_string.encode()).hexdigest()[:16]  # 取前16位作为短token
    return short_token


def check_access_token(m_token: str):
    headers = {
        "Authorization": m_token,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "max-age=0",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        # 可能还需要添加这些头
        'Connection': 'keep-alive',
        'sec-ch-ua': '"Not A(Brand";v="24", "Chromium";v="127"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1'
    }

    # 使用 session 发起请求
    resp = requests.get(
        url="https://chatgpt.com/backend-api/accounts/check/v4-2023-04-27?timezone_offset_min=-480",
        headers=headers,
        allow_redirects=True  # 允许重定向
    )
    # 打印响应信息
    print(resp.text)
    return resp
