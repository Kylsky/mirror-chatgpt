import json
import logging
import re
from io import BytesIO
from typing import Dict
from urllib.parse import urlparse

from flask import request, Response

import compress_utils
from utils.redis_util import RedisUtils


# 替换js内容
def modify_response_body(response, redis_util: RedisUtils) -> bytes:
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
        elif urlparse(response.url).path.startswith('/backend-api/conversations'):
            share_token = request.cookies.get("share_token")
            username = redis_util.hash_get("share_token_info:" + share_token, 'user_name')
            cur_user_conversations = redis_util.set_members('user_conversations:' + username)
            conversation_ids = [] if cur_user_conversations is None else cur_user_conversations
            # conversation_ids转换成map
            conversation_map = {}
            data = json.loads(content)
            # 获取用户对话
            for conversation_id in conversation_ids:
                conversation_map[conversation_id] = conversation_id
            for item in data['items']:
                print(conversation_map.get(item['id']))
                if conversation_map.get(item['id']) is None:
                    item['title'] = '🔒'
            return json.dumps(data).encode()
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


def need_auth(path: str) -> bool:
    return not any(path.endswith(ext) for ext in ('.js', '.css', '.webp'))


def body_need_handle(url: str) -> bool:
    parsed = urlparse(url)
    return (parsed.path.endswith(('.js', '.css'))
            or parsed.path == '/backend-api/me'
            or parsed.path.startswith('/backend-api/conversations'))


def set_if_not_empty(target_headers: Dict, source_headers: Dict, key: str) -> None:
    if key in source_headers:
        target_headers[key] = source_headers[key]


# 流式输出
def stream_response(user_name, response, redis_utils: RedisUtils):
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
