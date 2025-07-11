import redis
import json
from pathlib import Path

# 读取JSON配置文件
config = json.loads(Path('config.json').read_text())

# 提取Tair配置
TAIR_CONFIG = config['tair']

# 使用配置中的参数
host = TAIR_CONFIG['host']
port = TAIR_CONFIG['port']
pwd = TAIR_CONFIG['password']
TAIR_DB = 0
def connect_tair():
    try:
        # 创建连接池（推荐）
        pool = redis.ConnectionPool(
            host=host,
            port=port,
            password=pwd,
            db=TAIR_DB,
            decode_responses=True  # 自动解码返回值为字符串
        )
        client = redis.Redis(connection_pool=pool)

        # 测试连接
        if client.ping():
            print("✅ Tair连接成功")
            return client
        else:
            raise ConnectionError("Tair连接异常")

    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return None

# 使用示例
if __name__ == "__main__":
    tair_client = connect_tair()

    if tair_client:
        # 基本操作示例
        tair_client.set("demo_key", "Hello Tair!")
        value = tair_client.get("demo_key")
        print(f"获取值: {value}")  # 输出: Hello Tair!

        # 删除测试键
        tair_client.delete("demo_key")
