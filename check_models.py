import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load API Key
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print(" Lỗi: Chưa có GOOGLE_API_KEY trong file .env")
else:
    genai.configure(api_key=api_key)
    print(f" Đang kiểm tra với Key: {api_key[:10]}...")
    
    try:
        print("DANH SÁCH MODEL ĐƯỢC PHÉP DÙNG:")
        print("-" * 40)
        found_any = False
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"✅ Name: {m.name}")
                found_any = True
        
        if not found_any:
            print("Không tìm thấy model nào hỗ trợ chat (generateContent).")
            print("Có thể API Key của bạn chưa được kích hoạt Google AI Studio.")
            
    except Exception as e:
        print(f" Lỗi kết nối Google: {e}")