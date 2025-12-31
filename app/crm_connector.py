# app/crm_connector.py
import requests
import json
import os
import redis

# Cấu hình Charm.Contact (Sau này thay bằng URL thật)
CHARM_API_URL = os.getenv("CHARM_API_URL", "http://127.0.0.1:8000/mock-crm/leads")
CHARM_API_KEY = os.getenv("CHARM_API_KEY", "mock-key")

class CRMConnector:
    def __init__(self):
        # Kết nối Redis để làm hàng đợi Retry
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis = redis.from_url(redis_url)

    def push_lead(self, lead_data: dict):
        """
        Quy trình chuẩn:
        1. Check xem khách có chưa (Deduplication).
        2. Nếu chưa -> Tạo mới (Create).
        3. Nếu có rồi -> Cập nhật (Update).
        4. Nếu lỗi -> Đẩy vào Queue Retry.
        """
        print(f" Đang bắn Lead sang CRM: {lead_data['phone']}...")

        try:
            # --- BƯỚC 1: CHECK TRÙNG & GỬI (LOGIC GỘP) ---
            # Hầu hết CRM hiện đại (như Charm) có endpoint "Upsert" 
            # (tự check trùng bằng Phone/Email, nếu có thì update, chưa thì tạo mới).
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {CHARM_API_KEY}"
            }
            
            response = requests.post(
                CHARM_API_URL, 
                json=lead_data,
                headers=headers,
                timeout=10 # Đợi tối đa 10s
            )
            
            # --- BƯỚC 2: XỬ LÝ KẾT QUẢ ---
            if response.status_code in [200, 201]:
                print(f"✅ CRM Success: Deal ID {response.json().get('deal_id', 'Unknown')}")
                return True
                
            else:
                print(f" CRM Trả lỗi {response.status_code}: {response.text}")
                # Logic Retry nằm ở dưới
                raise Exception(f"CRM Error {response.status_code}")

        except Exception as e:
            # --- BƯỚC 3: CƠ CHẾ RETRY (CỨU HỘ DỮ LIỆU) ---
            print(f" LỖI KẾT NỐI CRM: {e}")
            print(" Đang đẩy vào hàng đợi Retry (crm_retry_queue)...")
            
            # Lưu dữ liệu vào Redis để Worker khác xử lý lại sau
            self.retry_push(lead_data)
            return False

    def retry_push(self, lead_data):
        """Đẩy lead bị lỗi vào Redis để thử lại sau"""
        try:
            self.redis.rpush("crm_retry_queue", json.dumps(lead_data))
        except Exception as e:
            print(f" LỖI NGHIÊM TRỌNG: Không thể lưu Retry! {e}")