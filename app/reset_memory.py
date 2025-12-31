import redis
import os
from dotenv import load_dotenv

load_dotenv()
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
r = redis.from_url(redis_url)

def reset_all():
    print("🧹 ĐANG DỌN DẸP BỘ NHỚ BOT...")
    
    # 1. Tìm tất cả các key liên quan đến Session và History
    keys_session = r.keys("session:*")
    keys_history = r.keys("history:*")
    keys_tags = r.keys("tags:*")
    
    all_keys = keys_session + keys_history + keys_tags
    
    if not all_keys:
        print("✅ Bộ nhớ đã sạch, không có gì để xóa.")
        return

    # 2. Xóa sạch
    for key in all_keys:
        r.delete(key)
        print(f"   - Đã xóa: {key.decode()}")
        
    print(f" ĐÃ XÓA XONG {len(all_keys)} BẢN GHI.")

if __name__ == "__main__":
    reset_all()