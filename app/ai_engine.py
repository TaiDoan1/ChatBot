# app/ai_engine.py
import google.generativeai as genai
import os
import json
from dotenv import load_dotenv

# Load API Key
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("❌ Lỗi: Chưa cấu hình GOOGLE_API_KEY")
else:
    genai.configure(api_key=api_key)

# ==============================================================================
# 1. SYSTEM PROMPT (BẢN GỐC TỪ TÀI LIỆU - DÙNG CHUNG TOÀN HỆ THỐNG)
# ==============================================================================
MASTER_SYSTEM_PROMPT = """
Bạn là AI Assistant cấp độ chuyên gia trong hệ thống AIHUB OS, đang vận hành cho nhiều thương hiệu khác nhau.

Vai trò của bạn:
• Trò chuyện với khách bằng giọng tự nhiên, gần gũi, tôn trọng, không phán xét.
• Luôn xưng hô theo cấu hình: call_me, call_user.
• Luôn tôn trọng brand_name và topic hiện tại.
• Không được hứa hẹn điều trị y khoa, chữa bệnh, chỉ được chia sẻ theo hướng: hỗ trợ, cải thiện, tham khảo, lộ trình thay đổi thói quen / lối sống.

Nhiệm vụ chính:
1. Hiểu khách muốn gì (intent).
2. Hỏi thêm các câu hỏi cần thiết theo flow_state.
3. Cá nhân hóa câu trả lời theo session_data (mức độ, thói quen, cảm xúc).
4. Chuẩn bị thông tin để hệ thống CRM chăm sóc và follow-up.

Bạn luôn phải:
• Giữ câu trả lời ngắn gọn, dễ hiểu, không dùng thuật ngữ khó.
• Một lần trả lời chỉ nên tập trung vào 1–2 ý chính, không nói lan man.
• Kết thúc mỗi câu trả lời bằng 1 câu hỏi mở nhẹ nhàng để dẫn flow.
• Nếu khách bối rối, lo lắng, từng thất bại trước đó, hãy động viên và hợp thức hóa cảm xúc của họ, không đổ lỗi.

Rất quan trọng:
• Bạn không tự tạo lead hay gọi API, bạn chỉ đề xuất meta-data (state, phân loại, tag) để hệ thống backend xử lý.
• Bạn phải trả lời theo đúng JSON format do hệ thống yêu cầu, không được thêm bớt text ngoài JSON.
"""

# ==============================================================================
# 2. USER PROMPT TEMPLATE (TEMPLATE ĐỘNG)
# ==============================================================================
USER_PROMPT_TEMPLATE = """
Bạn đang làm việc cho brand: {BRAND_NAME}
Chủ đề hiện tại (topic): {TOPIC}
Giọng điệu (tone): {TONE_STYLE}
Cách xưng hô: Bạn xưng là "{CALL_ME}" và gọi khách là "{CALL_USER}".

Trạng thái flow hiện tại (flow_state): {FLOW_STATE}

Dữ liệu đã biết về khách (session_data, JSON):
{SESSION_DATA_JSON}

Tin nhắn khách vừa gửi (user_message):
"{USER_MESSAGE}"

Yêu cầu:
1. Trả lời khách bằng tiếng Việt, đúng giọng điệu của {BRAND_NAME} và {TOPIC}.
2. Giữ câu trả lời từ 1–4 câu, thân thiện, rõ ràng, không lan man.
3. Dựa trên flow_state + session_data + user_message để:
   - Xác định bước tiếp theo (next_state) trong hành trình.
   - Nếu phù hợp, gợi ý xin số điện thoại (need_phone = true/false).
   - Phân loại khách (classification) theo topic hiện tại.
   - Gợi ý danh sách tags (tags[]) để hệ thống CRM gắn vào lead.

4. Trả về đúng **cấu trúc JSON sau**, không thêm chữ ngoài JSON:
{{
    "reply_text": "Câu trả lời gửi cho khách...",
    "next_state": "tên_state_tiếp_theo_hoặc_giữ_nguyên",
    "need_phone": true hoặc false,
    "classification": "chuỗi_mô_tả_phân_loại_khách (ví dụ: 'nghien_trung_binh')",
    "tags": ["tag1","tag2","tag3"]
}}
"""

def generate_ai_response(chat_history, config, session_data_json):
    """
    Hàm fill biến vào Template và gọi AI
    """
    # 1. Chuẩn bị dữ liệu để fill vào Template
    meta = config.get("meta_data", {})
    settings = config.get("system_settings", {})
    
    # Parse session data
    try:
        if isinstance(session_data_json, str):
            session_dict = json.loads(session_data_json)
        else:
            session_dict = session_data_json
    except:
        session_dict = {}

    # Lấy state hiện tại từ session
    current_state = session_dict.get("last_state", "START") 
    
    # Lấy tin nhắn cuối
    last_msg = chat_history[-1]["content"] if chat_history else ""

    # 2. Fill biến vào Template (Prompt Injection)
    user_prompt = USER_PROMPT_TEMPLATE.format(
        BRAND_NAME=meta.get("brand_default", "Unknown Brand"),
        TOPIC=config.get("topic_id", "general"),
        TONE_STYLE=meta.get("tone_style", "thân thiện"),
        CALL_ME=settings.get("call_me", "mình"),
        CALL_USER=settings.get("call_user", "bạn"),
        FLOW_STATE=current_state,
        SESSION_DATA_JSON=json.dumps(session_dict, ensure_ascii=False),
        USER_MESSAGE=last_msg
    )

    # 3. Gọi Model (Gemini 2.0 Flash)
    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash", 
            system_instruction=MASTER_SYSTEM_PROMPT, # <--- System Prompt Cố định
            generation_config={"response_mime_type": "application/json"}
        )
        
        # Gửi kèm lịch sử chat (tối ưu token, chỉ gửi 5 câu gần nhất + Prompt Template)
        # Lưu ý: Với Gemini, ta có thể gửi history qua biến history hoặc nhúng vào prompt. 
        # Để đơn giản và đúng template, ta gửi prompt template là nội dung chính.
        
        response = model.generate_content(user_prompt)
        return json.loads(response.text)
        
    except Exception as e:
        print(f"❌ Lỗi AI Engine: {e}")
        return {
            "reply_text": "Hệ thống đang bận xíu, anh/chị chờ em lát nha.",
            "next_state": "ERROR",
            "need_phone": False
        }