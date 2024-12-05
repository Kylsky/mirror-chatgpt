import redis
from typing import Any, Optional, List, Dict, Union
import json
from datetime import datetime, timedelta

class RedisUtils:
    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 0,
                 password: Optional[str] = None, decode_responses: bool = True):
        """
        初始化 Redis 连接

        Args:
            host: Redis 服务器地址
            port: Redis 端口
            db: 数据库索引
            password: Redis 密码
            decode_responses: 是否自动解码响应
        """
        self.redis_client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=decode_responses
        )

    def set_value(self, key: str, value: Any, expire_seconds: Optional[int] = None) -> bool:
        """
        设置键值对，支持自动序列化

        Args:
            key: 键名
            value: 值（支持各种数据类型）
            expire_seconds: 过期时间（秒）

        Returns:
            bool: 操作是否成功
        """
        try:
            # 如果是复杂数据类型，转换为 JSON
            if not isinstance(value, (str, int, float, bool)):
                value = json.dumps(value)

            self.redis_client.set(key, value)
            if expire_seconds:
                self.redis_client.expire(key, expire_seconds)
            return True
        except Exception as e:
            print(f"Error setting value: {str(e)}")
            return False

    def get_value(self, key: str, default: Any = None) -> Any:
        """
        获取值，支持自动反序列化

        Args:
            key: 键名
            default: 默认值

        Returns:
            解析后的值
        """
        try:
            value = self.redis_client.get(key)
            if value is None:
                return default

            # 尝试 JSON 解析
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        except Exception as e:
            print(f"Error getting value: {str(e)}")
            return default

    def delete_keys(self, *keys: str) -> int:
        """
        删除一个或多个键

        Args:
            keys: 要删除的键名

        Returns:
            int: 成功删除的键数量
        """
        try:
            return self.redis_client.delete(*keys)
        except Exception as e:
            print(f"Error deleting keys: {str(e)}")
            return 0

    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """
        递增计数器

        Args:
            key: 键名
            amount: 增加的数量

        Returns:
            Optional[int]: 增加后的值
        """
        try:
            return self.redis_client.incrby(key, amount)
        except Exception as e:
            print(f"Error incrementing value: {str(e)}")
            return None

    def hash_set(self, name: str, mapping: Dict[str, Any]) -> bool:
        """
        设置哈希表的多个字段

        Args:
            name: 哈希表名
            mapping: 字段映射字典

        Returns:
            bool: 操作是否成功
        """
        try:
            # 将复杂数据类型转换为 JSON
            processed_mapping = {
                k: json.dumps(v) if not isinstance(v, (str, int, float, bool)) else v
                for k, v in mapping.items()
            }
            self.redis_client.hmset(name, processed_mapping)
            return True
        except Exception as e:
            print(f"Error setting hash: {str(e)}")
            return False

    def hash_get(self, name: str, key: Optional[str] = None) -> Union[Dict, Any, None]:
        """
        获取哈希表的字段值

        Args:
            name: 哈希表名
            key: 字段名（为None时获取所有字段）

        Returns:
            Union[Dict, Any, None]: 字段值或字段字典
        """
        try:
            if key is None:
                # 获取所有字段
                result = self.redis_client.hgetall(name)
            else:
                # 获取单个字段
                result = self.redis_client.hget(name, key)

            # 尝试 JSON 解析
            if isinstance(result, dict):
                return {k: self._try_json_decode(v) for k, v in result.items()}
            return self._try_json_decode(result)
        except Exception as e:
            print(f"Error getting hash: {str(e)}")
            return None

    def list_push(self, name: str, *values: Any, left: bool = True) -> Optional[int]:
        """
        向列表添加元素

        Args:
            name: 列表名
            values: 要添加的值
            left: 是否从左侧添加

        Returns:
            Optional[int]: 添加后的列表长度
        """
        try:
            # 序列化复杂数据类型
            processed_values = [
                json.dumps(v) if not isinstance(v, (str, int, float, bool)) else v
                for v in values
            ]

            if left:
                return self.redis_client.lpush(name, *processed_values)
            return self.redis_client.rpush(name, *processed_values)
        except Exception as e:
            print(f"Error pushing to list: {str(e)}")
            return None

    def list_get_all(self, name: str) -> List[Any]:
        """
        获取列表所有元素

        Args:
            name: 列表名

        Returns:
            List[Any]: 列表中的所有元素
        """
        try:
            values = self.redis_client.lrange(name, 0, -1)
            return [self._try_json_decode(v) for v in values]
        except Exception as e:
            print(f"Error getting list: {str(e)}")
            return []

    def set_add(self, name: str, *values: Any) -> Optional[int]:
        """
        向集合添加元素

        Args:
            name: 集合名
            values: 要添加的值

        Returns:
            Optional[int]: 新添加的元素数量
        """
        try:
            processed_values = [
                json.dumps(v) if not isinstance(v, (str, int, float, bool)) else v
                for v in values
            ]
            return self.redis_client.sadd(name, *processed_values)
        except Exception as e:
            print(f"Error adding to set: {str(e)}")
            return None

    def set_members(self, name: str) -> List[Any]:
        """
        获取集合所有成员

        Args:
            name: 集合名

        Returns:
            List[Any]: 集合中的所有成员
        """
        try:
            values = self.redis_client.smembers(name)
            return [self._try_json_decode(v) for v in values]
        except Exception as e:
            print(f"Error getting set members: {str(e)}")
            return []

    def _try_json_decode(self, value: Any) -> Any:
        """
        尝试 JSON 解码

        Args:
            value: 要解码的值

        Returns:
            解码后的值
        """
        if value is None:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    def close(self):
        """关闭 Redis 连接"""
        self.redis_client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()