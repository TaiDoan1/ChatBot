# app/fb_helper.py
import os
import requests
import json

class FacebookClient:
    def __init__(self):
        # Lấy Token từ file .env
        self.page_access_token = os.getenv("FB_PAGE_ACCESS_TOKEN")
        self.api_url = "https://graph.facebook.com/v18.0/me/messages"

    def send_text_message(self, recipient_id, text):
        """
        Gửi tin nhắn văn bản trả lời khách hàng
        """
        if not self.page_access_token:
            print(" Chưa cấu hình FB_PAGE_ACCESS_TOKEN trong .env")
            return

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.page_access_token}"
        }
        
        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": text},
            "messaging_type": "RESPONSE"
        }

        try:
            response = requests.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status() # Báo lỗi nếu FB từ chối
            print(f" Đã gửi tin nhắn cho khách {recipient_id}: {text[:20]}...")
        except Exception as e:
            print(f" Lỗi gửi tin FB: {e}")
            if response:
                print(f"   Chi tiết FB báo: {response.text}")