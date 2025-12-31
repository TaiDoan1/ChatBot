# app/main.py
import os
import sys
from fastapi import FastAPI, Request, HTTPException
from app.config_loader import load_config
from app.fb_helper import FacebookClient
from app.schemas import LeadData # Import khuôn dữ liệu

# Khởi tạo App
app = FastAPI()

# Load biến môi trường
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "1234567890")
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Queue (Redis) để Worker xử lý sau
import redis
import json
r = redis.from_url(redis_url)

@app.get("/")
def home():
    return {"message": "Chatbot AIHUB is running!", "status": "ok"}

@app.get("/webhook")
def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            print("WEBHOOK_VERIFIED")
            return int(challenge)
        else:
            raise HTTPException(status_code=403, detail="Forbidden")
    return {"status": "ok"}

@app.post("/webhook")
async def handle_webhook(request: Request):
    body = await request.json()
    # Đẩy toàn bộ cục tin nhắn vào hàng đợi (Queue) để Worker xử lý
    r.rpush("chat_queue", json.dumps(body))
    return {"message": "Event received"}

# ==========================================
#  MOCK CRM API 
# ==========================================
@app.post("/mock-crm/leads")
async def receive_lead_from_bot(lead: LeadData):
    """
    Đây là cái túi hứng dữ liệu giả lập.
    """
    print("\n----------------------------------------")
    print("🌟 [MOCK CRM] ĐÃ NHẬN ĐƯỢC DEAL MỚI!")
    print(f"👤 Khách hàng: {lead.full_name}")
    print(f"📞 SĐT: {lead.phone} | 📧 Email: {lead.email}")
    
    # In các trường mới (Score, Intent, Class)
    print(f"🎯 Intent: {lead.intent}")
    print(f"📊 Phân loại: {lead.classification}")
    print(f"💯 Lead Score: {lead.score}/100")
    print(f"📝 Ghi chú AI: {lead.notes}")
    
    # In full data để debug
    # print(f"📦 Full Data: {lead.model_dump()}")
    print("----------------------------------------\n")
    
    return {
        "status": "success",
        "message": "Lead created successfully",
        "deal_id": "DEAL_NEW_9999"
    }