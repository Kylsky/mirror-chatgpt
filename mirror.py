import json
import logging
import os
import re
import ssl
import traceback
from urllib.parse import urlparse
import cloudscraper


# import requests
import yaml
from flask import Flask, request, Response, render_template, make_response, redirect

import models
from entity.CloudFlareSession import test_cookies
from entity.share import Share
from utils.common_util import build_url, build_target_url, need_auth, stream_response, body_need_handle, \
    modify_response_body
from utils.redis_util import RedisUtils
from utils.token_util import access_to_share, check_access_token

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

scraper = cloudscraper.create_scraper()

redis_utils = RedisUtils(
    host=os.getenv('REDIS_HOST', '127.0.0.1'),
    port=int(os.getenv('REDIS_PORT', 6379))
)

cf_cookie = []
user_agent_map = {}


class Config:
    def __init__(self, config_path: str = "config.yml"):
        with open(config_path) as f:
            config = yaml.safe_load(f)
        self.tls = config['mirror'].get('tls', {})
        self.tls_enabled = self.tls.get('enabled', False)
        self.tls_cert = self.tls.get('cert')
        self.tls_key = self.tls.get('key')
        self.proxy = self.tls.get('proxy')
        self.port = config['mirror']['port']
        self.redirect_uri = config['mirror']['redirect_uri']


# 账号信息接口
@app.route('/api/check', methods=['GET'])
def api_check():
    m_token = request.args.get("m_token", None)
    if m_token is not None:
        resp = check_access_token(m_token)
        response = Response(
            response=resp.content,
            status=resp.status_code
        )
    else:
        response = Response(
            response=None,
            status=401
        )
    return response


# 账号信息接口
@app.route('/api/get-cf-list', methods=['GET'])
def api_get_cf_list():
    data = test_cookies()
    return data


@app.route('/api/set-cf-cookie', methods=['POST'])
def api_set_cf_cookie():
    global cf_cookie
    cf_cookie = request.get_json()['cookies']
    user_agent_map[request.get_json()['proxy_url']] = request.get_json()['user_agent']
    return ""


# 免登接口
@app.route('/api/free-login', methods=['GET'])
def api_free_login():
    share_token = request.args.get("share_token", None)

    # 不为空，获取at并校验
    if share_token is not None:
        access_token = redis_utils.hash_get('share_token_info:' + share_token, 'access_token')
        # at为空，返回
        if access_token is None:
            redirect_path = redirect(config.redirect_uri)
            response = make_response(redirect_path)
            return response
        else:
            # resp = check_access_token(str(access_token))
            # at校验失败，返回
            # if resp.status_code != 200:
            #     redirect_path = redirect(config.redirect_uri)
            #     response = make_response(redirect_path)
            #     return response
            # else:
            response = make_response(redirect('/'))
            response.set_cookie('share_token', share_token)
            # for cf_ck in cf_cookie:
            #     response.set_cookie(cf_ck['name'], cf_ck['value'])
            return response
    else:
        redirect_path = redirect(config.redirect_uri)
        response = make_response(redirect_path)
        return response


# 生成share_token
@app.route('/api/share', methods=['POST'])
def api_share():
    share_info = request.get_json(silent=True)
    # 转换为实体类
    share = Share(**share_info)
    # resp = check_access_token(share.access_token)
    # 校验token状态，不通过直接返回false
    # if resp.status_code != 200:
    #     response = {'status': False, 'message': '无效的 access token', 'data': None}
    #     return response

    # 生成share_token
    share_token = access_to_share(share)

    # 检查原有用户信息,如果存在需要删除
    former_share_token = redis_utils.get_value('user_info:' + share.user_name)
    if former_share_token is not None:
        redis_utils.delete_keys("share_token_info:" + former_share_token)
    # 将share_token存入redis
    redis_utils.hash_set("share_token_info:" + share_token, share_info)
    # 将用户信息存入redis
    redis_utils.set_value("user_info:" + share.user_name, share_token)

    # 返回share_token
    response = {'status': True, 'message': 'Success', 'data': share_token}
    print("生成的share_token: ", share_token)
    return response


# 处理登出
@app.route('/backend-api/accounts/logout_all', methods=['POST'])
def handle_logout():
    return '', 403


# 处理首页
@app.route('/')
@app.route('/c/<path:path>')
@app.route('/g/<path:path>')
def handle_index(path: str = None):
    response = make_response(render_template(
        'index.html',
        StaticPrefixUrl=f"{request.scheme}://{request.host}",
        Token="",
        REDIRECT_URI=config.redirect_uri
    ))
    return response


@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def proxy(path: str):
    access_token = request.headers.get('Authorization')
    share_token = request.cookies.get("share_token")
    if access_token is not None and access_token.startswith("Bearer "):
        access_token = access_token.replace("Bearer ", "")
    elif access_token is None and share_token is not None:
        access_token = redis_utils.hash_get("share_token_info:" + share_token, 'access_token')
        if access_token is None:
            return '', 401
    else:
        return '', 401

    source_url = build_url(request)
    target_url = build_target_url(source_url)

    headers = {
        k: v for k, v in request.headers.items()
        if not models.filter_header(k)
    }

    headers['Referer'] = target_url
    headers['Origin'] = f"https://{urlparse(target_url).netloc}"

    if path.endswith(".map") or path.endswith(".woff2"):
        return '', 405
    if need_auth(path):
        if access_token != '':
            headers[
                'Authorization'] = f"Bearer {access_token}"
            # 设置cookie
            header_ck = 'share_token=' + share_token if share_token is not None else ''
            global cf_cookie
            for cf_ck in cf_cookie:
                if cf_ck['name'] != '__cf_bm':
                    header_ck += ';' + cf_ck['name'] + "=" + cf_ck['value']
            headers['Cookie'] = header_ck
        else:
            # 重定向
            return '', 401

    # Forward the request
    px = {
        'http': os.getenv("PROXY", ""),
        'https': os.getenv("PROXY", "")
    }
    try:
        resp = scraper.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=request.get_data(),
            stream=True if path == 'backend-api/conversation' else False,  # 只在会话API时使用流式传输
            allow_redirects=False,
            proxies=px

        )
        print(headers)
    except scraper.RequestException as e:
        traceback.print_exc()
        return str(e), 500

    share_token = request.cookies.get("share_token")
    username = redis_utils.hash_get("share_token_info:" + share_token, 'user_name') if share_token is not None else ''
    # conversation 接口采取流式输出
    if path == 'backend-api/conversation':
        data = stream_response(username, resp, redis_utils)
        # 使用正则表达式匹配具有特定格式的 JSON
        json_pattern = re.compile(r'{"type": "conversation_detail_metadata".*?}')

        # 查找匹配的 JSON
        match = json_pattern.search(str(data.get_data()))
        if match:
            json_str = match.group(0)
            try:
                json_data = json.loads(json_str)
                # 这里处理找到的 JSON 数据
                # 可以访问具体字段
                conversation_id = json_data.get('conversation_id')
                # redis_utils.set_value(f'conversation_metadata:{conversation_id}', json_data)
                redis_utils.set_add('user_conversations:' + username, conversation_id)
            except json.JSONDecodeError:
                pass
        return data
    if path.startswith('backend-api/conversation/') and path.find('init') == -1:
        cur_conversation = path.split("/")[2]
        cur_user_conversations = redis_utils.set_members('user_conversations:' + username)
        # 判断cur_conversation是否在用户对话列表中
        if cur_user_conversations is None or cur_conversation not in cur_user_conversations:
            return '', 401

    # 处理响应
    response_headers = {}
    for header in ['Content-Type', 'Cache-Control', 'Expires']:
        if header in resp.headers:
            response_headers[header] = resp.headers[header]

    # 对于静态文件和需要处理的响应
    if body_need_handle(target_url):
        modified_content = modify_response_body(resp, redis_utils)
        response = Response(
            response=modified_content,
            status=resp.status_code,
            headers=response_headers
        )
    else:
        # 对于其他请求，直接返回原始响应
        response = Response(
            response=resp.content,
            status=resp.status_code,
            headers=response_headers
        )

    return response


def main():
    global config
    config = Config()

    if config.tls_enabled:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(config.tls_cert, config.tls_key)
        app.run(
            host="0.0.0.0",
            port=config.port,
            ssl_context=ssl_context
        )
    else:
        app.run(
            host="0.0.0.0",
            port=config.port
        )


if __name__ == '__main__':
    main()
