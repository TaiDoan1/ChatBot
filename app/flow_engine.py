# app/flow_engine.py
import re
import json
from app.schemas import LeadData

class FlowEngine:
    def __init__(self, redis_client):
        self.redis = redis_client

    def calculate_score(self, phone, email, stage, classification):
        """
        Hàm chấm điểm Lead (Lead Scoring Algorithm)
        Thang điểm: 0 - 100
        """
        score = 10 # Điểm sàn cho bất kỳ ai nhắn tin
        
        # 1. Điểm hạ tầng (Contact Info) -> Quan trọng nhất
        if phone or email: 
            score += 50
        
        # 2. Điểm phân loại (AI Classification)
        classification = (classification or "").lower()
        if "nghien_nang" in classification: score += 15  # Khách đau khổ -> Dễ chốt
        if "vip" in classification: score += 20          # Khách tiền nhiều
        if "stress" in classification: score += 10       # Khách có vấn đề tâm lý cần giải quyết
        
        # 3. Điểm giai đoạn (Pipeline Stage)
        stage = (stage or "").upper()
        if stage == "HOT": score += 20
        elif stage == "WARM": score += 10
        elif stage == "QUALIFIED": score += 5
        
        # Giới hạn max 100
        return min(score, 100)

    def process_ai_result(self, sender_id, message_text, ai_json, config):
        """
        TRÁI TIM LOGIC: Điều phối dữ liệu từ AI sang CRM
        """
        # -------------------------------------------------------
        # 1. BÓC TÁCH DỮ LIỆU AN TOÀN (SAFE PARSING)
        # -------------------------------------------------------
        # Dùng 'or' để ưu tiên key mới, fallback về key cũ, cuối cùng là mặc định
        reply_text = ai_json.get("reply_text") or ai_json.get("reply_to_user") or "..."
        
        # Lấy các object con (đảm bảo không None)
        analysis = ai_json.get("analysis") or {}
        detected_info = ai_json.get("detected_info") or {}
        tags = ai_json.get("tags") or []
        
        # Lấy các biến Meta-data mới
        classification = ai_json.get("classification") or ""
        need_phone = ai_json.get("need_phone", False)
        next_state = ai_json.get("next_state") or "DEFAULT"
        
        # Xác định Intent (Mục đích)
        # Nếu AI không trả intent riêng, lấy tạm sub_topic
        sub_topic = analysis.get("sub_topic") or ""
        intent = ai_json.get("intent") or sub_topic or "general_inquiry"

        # -------------------------------------------------------
        # 2. SĂN TÌM SĐT & EMAIL (REGEX + AI SUPPORT)
        # -------------------------------------------------------
        phone = self.extract_phone_number(message_text)
        email = self.extract_email(message_text)
        
        # Nếu Regex thất bại, thử niềm tin vào AI
        if not phone and detected_info: 
            phone = detected_info.get("phone")
        if not email and detected_info:
            email = detected_info.get("email")

        # -------------------------------------------------------
        # 3. XÁC ĐỊNH PIPELINE STAGE (TỰ ĐỘNG PHÂN PHỄU)
        # -------------------------------------------------------
        stage = "NEW" # Mặc định: Khách mới chưa biết gì
        
        # Level 2: QUALIFIED (AI đã phân loại được khách -> Không phải spam)
        if classification and classification.lower() != "unknown":
            stage = "QUALIFIED"
            
        # Level 3: WARM (Khách có intent mua hàng hoặc AI đánh giá tốt)
        if "warm" in classification.lower() or "muon_mua" in intent.lower():
            stage = "WARM"
            
        # Level 4: HOT (Có SĐT/Email -> Sale phải gọi ngay lập tức)
        if phone or email:
            stage = "HOT"

        # Tính điểm Score sau khi đã có Stage
        lead_score = self.calculate_score(phone, email, stage, classification)

        # -------------------------------------------------------
        # 4. ĐÓNG GÓI DỮ LIỆU (LEAD SCHEMA CHUẨN)
        # -------------------------------------------------------
        # Logic Notes: Gộp nhiều thông tin vào ghi chú để Sale đọc nhanh
        ai_notes = analysis.get('customer_behavior_notes', '')
        full_notes = f"[AI]: {ai_notes} | Stage: {stage} | Class: {classification}"

        lead = LeadData(
            full_name=f"User {sender_id}",
            phone=phone,
            email=email,
            facebook_uid=str(sender_id),
            profile_link=f"https://facebook.com/{sender_id}",
            
            # Phân loại
            topic=config.get("topic_id") or config.get("topic", "general"),
            subtopic=sub_topic,
            tags=tags,
            intent=intent,
            classification=classification,
            
            # Nguồn
            lead_source="facebook_chatbot",
            source_page=config.get("page_name", "Unknown Page"),
            channel="facebook",
            
            # Đánh giá & Dữ liệu thô
            data_raw=message_text,
            score=lead_score,
            
            # Ghi chú & Stage (Nếu schema có field stage thì map vào, ko thì để trong note)
            notes=full_notes
            # funnel_stage=stage (Bỏ comment dòng này nếu anh đã thêm field này vào schemas.py)
        )

        # -------------------------------------------------------
        # 5. QUYẾT ĐỊNH HÀNH ĐỘNG (ACTION DECISION)
        # -------------------------------------------------------
        action_signal = "REPLY"
        
        # CHỈ ĐẨY CRM KHI ĐẠT MỤC TIÊU TỐI THƯỢNG (CÓ DATA LIÊN HỆ)
        if phone or email:
            action_signal = "PUSH_CRM"
            print(f"💎 ĐÃ BẮT ĐƯỢC SĐT/EMAIL -> KÍCH HOẠT PUSH CRM NGAY!")
            
        # (Tùy chọn) Chỉ báo CRM nếu khách cực kỳ Hot (Score > 80) để Sale vào chat tay
        elif lead_score >= 80:
            action_signal = "PUSH_CRM"
            print(f"🔥 KHÁCH RẤT TIỀM NĂNG (Score {lead_score}) -> Báo CRM để Sale hỗ trợ")
            
        else:
            # Còn lại: Chỉ chat, không làm phiền CRM
            print(f"💬 Đang dẫn dắt... (Chưa có SĐT -> Không đẩy CRM)")

        # -------------------------------------------------------
        # 6. LƯU TRẠNG THÁI HỘI THOẠI (STATE MANAGEMENT)
        # -------------------------------------------------------
        if self.redis:
            # Chỉ cập nhật state nếu AI có đề xuất state mới
            if next_state and next_state != "DEFAULT":
                self.redis.hset(f"session:{sender_id}", "current_state", next_state)
            
            # Lưu tags vào Redis để dùng cho các logic sau
            for tag in tags:
                self.redis.rpush(f"tags:{sender_id}", tag)

        return {
            "text_to_send": reply_text,
            "action": action_signal,
            "lead_data": lead.to_dict()
        }

    # ====================================================
    # 👇 CÁC HÀM REGEX "BỌC THÉP" (KHÔNG BAO GIỜ CRASH) 👇
    # ====================================================

    def extract_phone_number(self, text):
        """Tìm SĐT VN (An toàn tuyệt đối)"""
        if not text: return None
        # Xóa nhiễu
        clean_text = text.replace('.', '').replace('-', '').replace(' ', '')
        # Regex: Đầu 03,05,07,08,09 + 8 số
        matches = re.findall(r'0[3|5|7|8|9]\d{8}', clean_text)
        return matches[0] if matches else None

    def extract_email(self, text):
        """Tìm Email (An toàn tuyệt đối)"""
        if not text: return None
        match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        return