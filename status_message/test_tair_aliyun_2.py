import redis
import json
from pathlib import Path

# 读取JSON配置文件
config = json.loads(Path('config.json').read_text())

# 提取Tair配置
TAIR_CONFIG = config['tair']

r = redis.Redis(host=TAIR_CONFIG['host'], port=TAIR_CONFIG['port'], password=TAIR_CONFIG['password'])
r.set('foo', 'bar')
print(r.get('foo'))