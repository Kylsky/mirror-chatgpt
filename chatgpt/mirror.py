from io import BytesIO

from flask import Flask, request, Response, render_template, make_response, redirect
import requests
from urllib.parse import urlparse
import json
from datetime import datetime, timedelta
from typing import Dict
import ssl

import yaml

import logging

from chatgpt import compress_utils
from chatgpt import models

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


class Config:
    def __init__(self, config_path: str = "config.yml"):
        with open(config_path) as f:
            config = yaml.safe_load(f)
        self.tls = config['mirror'].get('tls', {})
        self.tls_enabled = self.tls.get('enabled', False)
        self.tls_cert = self.tls.get('cert')
        self.tls_key = self.tls.get('key')
        self.host = config['mirror']['host']
        self.port = config['mirror']['port']
        self.token = config['mirror']['token']
        self.redirect_uri = config['mirror']['redirect_uri']


def build_target_url(source_url: str) -> str:
    parsed = urlparse(source_url)

    if parsed.path.startswith('/assets'):
        host = 'cdn.oaistatic.com'
        path = parsed.path
    elif parsed.path.startswith('/ab'):
        host = 'ab.chatgpt.com'
        path = parsed.path[3:]  # Remove /ab prefix
    else:
        host = 'chatgpt.com'
        path = parsed.path

    return f"https://{host}{path}"


def build_url(request_obj) -> str:
    scheme = 'https' if request_obj.is_secure else 'http'
    return f"{scheme}://{request_obj.host}{request_obj.full_path}"


def deal_token(token: str = None) -> str:
    if token is not None and token.startswith('eyJhbGci'):
        return token
    return config.token


def need_auth(path: str) -> bool:
    return not any(path.endswith(ext) for ext in ('.js', '.css', '.webp'))


def body_need_handle(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.path.endswith(('.js', '.css')) or parsed.path == '/backend-api/me'


def set_if_not_empty(target_headers: Dict, source_headers: Dict, key: str) -> None:
    if key in source_headers:
        target_headers[key] = source_headers[key]


@app.route('/')
@app.route('/c/<path:path>')
@app.route('/g/<path:path>')
def handle_index(path: str = None):
    response = make_response(render_template(
        'index.html',
        StaticPrefixUrl=f"{request.scheme}://{request.host}",
        Token=""
    ))
    return response


@app.route('/backend-api/accounts/logout_all', methods=['POST'])
def handle_logout():
    return '', 403


def modify_response_body(response) -> bytes:
    try:
        content = response.content  # 直接获取完整内容，而不是使用raw流
        if not content:
            return b''

        if urlparse(response.url).path == '/backend-api/me':
            try:
                data = json.loads(content)
                data['email'] = 'sam@openai.com'
                data['phone_number'] = None
                data['name'] = 'Sam Altman'
                for org in data['orgs']['data']:
                    org['description'] = f"Personal org for {data['email']}"
                return json.dumps(data).encode()
            except json.JSONDecodeError:
                return content
        else:
            # 对于静态文件的处理
            try:
                text_content = content.decode('utf-8')
                text_content = (
                    text_content
                    .replace('https://chatgpt.com', f"{request.scheme}://{request.host}")
                    .replace('https://ab.chatgpt.com', f"{request.scheme}://{request.host}/ab")
                    .replace('https://cdn.oaistatic.com', f"{request.scheme}://{request.host}")
                    .replace('chatgpt.com', request.host)
                )
                return text_content.encode('utf-8')
            except UnicodeDecodeError:
                # 如果不是文本文件，直接返回原内容
                return content
    except Exception as e:
        logging.error(f"Error modifying response body: {e}")
        return response.content


@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def proxy(path: str):
    source_url = build_url(request)
    target_url = build_target_url(source_url)

    # Build headers
    headers = {
        k: v for k, v in request.headers.items()
        if not models.filter_header(k)
    }

    headers['Referer'] = target_url
    headers['Origin'] = f"https://{urlparse(target_url).netloc}"

    if path.endswith(".map"):
        return '', 405
    if need_auth(path):
        token = deal_token()
        if token != '':
            headers[
                'Authorization'] = f"Bearer {token}"
        else:
            # 重定向
            print("token为空，重定向至首页")
            redirect(config.redirect_uri)

    # Forward the request
    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=request.get_data(),
            stream=True if path == 'backend-api/conversation' else False,  # 只在会话API时使用流式传输
            allow_redirects=False
        )
    except requests.RequestException as e:
        return str(e), 500

    # Handle special cases
    if path == 'backend-api/conversation':
        return stream_response(resp)

    # 处理响应
    response_headers = {}
    for header in ['Content-Type', 'Cache-Control', 'Expires']:
        if header in resp.headers:
            response_headers[header] = resp.headers[header]

    # 对于静态文件和需要处理的响应
    if body_need_handle(target_url):
        modified_content = modify_response_body(resp)
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


def stream_response(response):
    def generate():
        content_encoding = response.headers.get('Content-Encoding')
        reader = compress_utils.wrap_reader(response.raw, content_encoding)
        writer = compress_utils.wrap_writer(BytesIO(), content_encoding)

        while True:
            chunk = reader.read(1)
            if not chunk:
                break
            writer.write(chunk)
            yield chunk

    response_headers = {
        k: v for k, v in response.headers.items()
        if k in ['Content-Encoding', 'Content-Type']
    }

    return Response(
        generate(),
        status=response.status_code,
        headers=response_headers
    )


def main():
    global config
    config = Config()

    if config.tls_enabled:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(config.tls_cert, config.tls_key)
        app.run(
            host=config.host,
            port=config.port,
            ssl_context=ssl_context
        )
    else:
        app.run(
            host=config.host,
            port=config.port
        )


if __name__ == '__main__':
    main()
