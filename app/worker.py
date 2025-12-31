import os
import sys
import datetime
import time 

# Thêm đường dẫn gốc
sys.path.append(os.getcwd())

import redis
import json
from dotenv import load_dotenv

from app.config_loader import load_config
from app.ai_engine import generate_ai_response
from app.flow_engine import FlowEngine
from app.fb_helper import FacebookClient
from app.crm_connector import CRMConnector

# --- CẤU HÌNH THỜI GIAN CHỜ ---
HANDOFF_TIMEOUT_SECONDS = 60 # 1 phút (Nếu Admin im lặng 60s, Bot sẽ bật lại)
# Nếu anh biết ID App của Bot, điền vào .env: BOT_APP_ID=123456...
BOT_APP_ID = os.getenv("BOT_APP_ID") 
# -----------------------------

# 1. Khởi tạo
load_dotenv()
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.from_url(redis_url)

flow_engine = FlowEngine(redis_client)
fb_client = FacebookClient() 
crm = CRMConnector()

print(f" WORKER ĐANG CHẠY... (Auto Handoff: {HANDOFF_TIMEOUT_SECONDS}s)")

# ====================================================
# 👇 KHU VỰC QUẢN LÝ SESSION & MEMORY
# ====================================================

def get_chat_history(sender_id):
    """Lấy lịch sử chat"""
    key = f"history:{sender_id}"
    raw_list = redis_client.lrange(key, -10, -1) 
    history = []
    for item in raw_list:
        try:
            history.append(json.loads(item))
        except:
            pass
    return history

def save_chat_history(sender_id, role, content):
    """Lưu tin nhắn mới"""
    key = f"history:{sender_id}"
    message = json.dumps({"role": role, "content": content})
    redis_client.rpush(key, message)
    redis_client.ltrim(key, -50, -1)

def get_session(sender_id):
    """Lấy Context khách hàng"""
    key = f"session:{sender_id}"
    data = redis_client.hgetall(key)
    session = {k.decode(): v.decode() for k, v in data.items()}
    
    if "data" in session:
        try:
            session["data"] = json.loads(session["data"])
        except:
            session["data"] = {}
    else:
        session["data"] = {}
        
    session["conversation_mode"] = session.get("conversation_mode", "BOT")
    try:
        session["last_human_activity"] = float(session.get("last_human_activity", 0))
    except:
        session["last_human_activity"] = 0.0

    return session

def update_session(sender_id, page_id, topic, state, new_data=None, 
                   conversation_mode=None, last_human_activity=None): 
    """Lưu Session chuẩn Schema"""
    key = f"session:{sender_id}"
    
    current_data_str = redis_client.hget(key, "data")
    current_data = json.loads(current_data_str) if current_data_str else {}
    
    if new_data:
        current_data.update(new_data)
    
    update_payload = {
        "user_id": sender_id,
        "page_id": page_id, 
        "topic": topic,
        "state": state,
        "data": json.dumps(current_data),
        "updated_at": datetime.datetime.now().isoformat()
    }

    if conversation_mode:
        update_payload["conversation_mode"] = conversation_mode
    if last_human_activity is not None:
        update_payload["last_human_activity"] = str(last_human_activity) 

    redis_client.hset(key, mapping=update_payload)
    redis_client.expire(key, 86400 * 3) 

# ====================================================
# 👇 VÒNG LẶP XỬ LÝ CHÍNH
# ====================================================

def process_message():
    while True:
        try:
            packed_item = redis_client.blpop("chat_queue", timeout=5)
            if not packed_item: continue 

            raw_json = packed_item[1]
            body = json.loads(raw_json)

            for entry in body.get("entry", []):
                page_id = str(entry.get("id")) 
                
                # --- LOAD CONFIG ---
                config = load_config(page_id)
                if not config:
                    print(f"❌ Không tìm thấy Config cho Page {page_id}")
                    continue
                
                page_name = config.get("page_name")
                if not page_name:
                    page_name = config.get("meta_data", {}).get("brand_default", "Unknown")
                config["page_name"] = page_name
                topic_id = config.get("topic_id", "general")
                # -------------------

                for messaging in entry.get("messaging", []):
                    message_obj = messaging.get("message", {})
                    
                    # 1. LOGIC PHÁT HIỆN ADMIN/ECHO (ĐÃ CẬP NHẬT)
                    is_echo = message_obj.get("is_echo", False)
                    sender_id = str(messaging.get("sender", {}).get("id"))
                    recipient_id = str(messaging.get("recipient", {}).get("id"))
                    
                    # Một tin nhắn là từ Page nếu is_echo=True HOẶC sender_id == page_id
                    if is_echo or (sender_id == page_id):
                        msg_app_id = str(message_obj.get("app_id", ""))
                        admin_text = message_obj.get("text", "")
                        
                        # 👇👇👇 ĐÃ MỞ LOG NÀY ĐỂ ANH CHECK APP ID 👇👇👇
                        print(f"DEBUG ECHO: app_id={msg_app_id}, text={admin_text}")

                        # --- KIỂM TRA XEM CÓ PHẢI BOT TỰ GỬI KHÔNG ---
                        # Nếu trong .env có cấu hình BOT_APP_ID và khớp với msg_app_id -> Bỏ qua
                        if BOT_APP_ID and msg_app_id == BOT_APP_ID:
                            # print("🤖 [IGNORE] Tin nhắn từ Bot.")
                            continue
                        
                        # --- XÁC NHẬN LÀ ADMIN ---
                        print(f"\n👮 [DETECTED ADMIN] AppID: {msg_app_id} | Text: {admin_text[:20]}...")
                        
                        target_user_id = recipient_id # Khách hàng là người nhận
                        
                        sess = get_session(target_user_id)
                        curr_state = sess.get("state", "START")
                        
                        # Kích hoạt HUMAN MODE
                        update_session(
                            sender_id=target_user_id,
                            page_id=page_id,
                            topic=topic_id,
                            state=curr_state,
                            conversation_mode="HUMAN", 
                            last_human_activity=time.time() 
                        )
                        print(f"   => Đã chuyển {target_user_id} sang HUMAN MODE.")
                        continue 

                    # 2. XỬ LÝ TIN NHẮN TỪ KHÁCH HÀNG
                    message_text = message_obj.get("text")
                    if not message_text: continue 

                    print(f"\n📨 User {sender_id}: {message_text}")

                    session_obj = get_session(sender_id)
                    current_state = session_obj.get("state", "START")
                    session_data_json = session_obj.get("data", {})
                    
                    mode = session_obj["conversation_mode"]
                    last_human_activity = session_obj["last_human_activity"]
                    current_time = time.time()

                    # --- LOGIC TỰ ĐỘNG BẬT/TẮT BOT ---
                    if mode == "HUMAN":
                        silence_duration = current_time - last_human_activity
                        
                        if silence_duration > HANDOFF_TIMEOUT_SECONDS:
                            print(f"⏰ [AUTO RESUME] Admin im lặng {int(silence_duration)}s > {HANDOFF_TIMEOUT_SECONDS}s. Bot bật lại.")
                            mode = "BOT"
                        else:
                            print(f"🤫 [HUMAN MODE] Bot đang im lặng. (Admin mới chat cách đây {int(silence_duration)}s)")
                            continue 

                    # 3. NẾU LÀ BOT MODE -> GỌI AI XỬ LÝ
                    history = get_chat_history(sender_id)
                    current_history = history + [{"role": "user", "content": message_text}]

                    ai_json = generate_ai_response(current_history, config, json.dumps(session_data_json))
                    
                    final_result = flow_engine.process_ai_result(sender_id, message_text, ai_json, config)
                    reply_text = final_result["text_to_send"]
                    lead_data = final_result["lead_data"]

                    next_state = ai_json.get("next_state") or current_state
                    new_data_points = {}
                    if lead_data.get("classification"):
                        new_data_points["classification"] = lead_data.get("classification")
                    if lead_data.get("subtopic"):
                        new_data_points["subtopic"] = lead_data.get("subtopic")
                    
                    # Cập nhật Session (Giữ nguyên mode là BOT)
                    update_session(
                        sender_id=sender_id,
                        page_id=page_id,
                        topic=topic_id,
                        state=next_state,
                        new_data=new_data_points,
                        conversation_mode="BOT", 
                        last_human_activity=0 
                    )

                    fb_client.send_text_message(sender_id, reply_text)
                    save_chat_history(sender_id, "user", message_text)
                    save_chat_history(sender_id, "model", reply_text)

                    if final_result["action"] == "PUSH_CRM":
                        print(f"💎 DATA LEAD -> CRM...")
                        crm.push_lead(lead_data)

        except Exception as e:
            print(f"❌ Worker Lỗi: {e}")
            time.sleep(1)

if __name__ == "__main__":
    process_message()