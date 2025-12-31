# app/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional

class LeadData(BaseModel):
    """
    Schema chuẩn hóa (Đã bao gồm cả Email để tránh lỗi hệ thống)
    """
    # 1. Thông tin cơ bản
    full_name: str = "Unknown"
    phone: Optional[str] = None
    email: Optional[str] = None  
    
    facebook_uid: str
    profile_link: str = ""
    
    # 2. Phân loại
    topic: str              
    subtopic: str = ""      
    tags: List[str] = []    
    intent: str = ""        
    classification: str = "" 
    
    # 3. Nguồn & Kênh
    lead_source: str = "facebook_chatbot"
    source_page: str        
    channel: str = "facebook"
    
    # 4. Dữ liệu thô & Đánh giá
    data_raw: str = ""      
    score: int = 10         
    
    # Phụ trợ
    notes: str = ""

    def to_dict(self):
        return self.model_dump()