# test_cache.py
from utils.cache import cache
import time

print("="*50)
print("Redis 缓存测试")
print("="*50)

# 测试写入
print("\n1. 写入缓存...")
cache.set("test_key", "Hello OOP Platform", timeout=10)
print("✅ 写入成功")

# 测试读取
print("\n2. 读取缓存...")
value = cache.get("test_key")
print(f"✅ 读取成功: {value}")

# 测试过期
print("\n3. 等待 11 秒后测试过期...")
for i in range(11):
    print(f"   第 {i+1} 秒...")
    time.sleep(1)

value = cache.get("test_key")
if value is None:
    print("✅ 缓存已过期，功能正常")
else:
    print(f"❌ 缓存未过期: {value}")

print("\n" + "="*50)
print("测试完成！")