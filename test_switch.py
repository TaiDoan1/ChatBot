# test_switch.py
import sys
import os

# Thêm đường dẫn để python tìm thấy module app
sys.path.append(os.getcwd())

from app.config_loader import load_config
from app.ai_engine import generate_ai_response

def main():
    print("--- TUI TEST CON BOT ĐA NHÂN CÁCH NÀY HIHI ---")
    print("1. Page Biohacking 360 (Y tế)")
    print("2. Page Luxury Realty (Bất động sản)")
    
    # 1. Cho anh chọn vai diễn
    choice = input("\n Bạn muốn test Page nào? nhập số 1(y tế), số 2(bds) ")
    
    if choice == "1":
        page_id = "1001"
        print("\nĐang load kịch bản BÁC SĨ...")
    elif choice == "2":
        page_id = "1002"
        print("\nĐang load kịch bản SALE BĐS...")
    else:
        print(" Chọn sai rồi đại ca!")
        return

    # 2. Load Config tương ứng
    config = load_config(page_id)
    if not config:
        print("❌ Lỗi: Không đọc được file config!")
        return

    # Lấy Prompt từ config ra
    prompt_kich_ban = config["system_prompt"]
    chat_history = []

    print(f"\nBẮT ĐẦU CHAT VỚI: {config['page_name']} ---")
    print("(Gõ 'exit' để thoát, gõ 'switch' để đổi page khác)\n")

    # 3. Vòng lặp chat
    while True:
        user_input = input("Tui là khách: ")
        
        if user_input.lower() in ["exit", "quit"]:
            break
        
        # 4. Gọi AI với đúng kịch bản đã load
        chat_history.append({"role": "user", "content": user_input})
        
        try:
            ai_data = generate_ai_response(chat_history, prompt_kich_ban)
            bot_reply = ai_data.get("reply_to_user", "Lỗi...")
            
            print(f"Bot Tài -.-: {bot_reply}")
            # print(f"   [Tag]: {ai_data.get('tags')}")
            
            chat_history.append({"role": "assistant", "content": bot_reply})
            
        except Exception as e:
            print(f"❌ Lỗi: {e}")

if __name__ == "__main__":
    main()