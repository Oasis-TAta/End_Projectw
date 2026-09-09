import requests

# ============================================================================
# ตั้งค่า LINE Messaging API (LINE Bot)
# ไปที่: https://developers.line.biz/
# ============================================================================
CHANNEL_ACCESS_TOKEN = "o0zzC6RLeIndl2FnSgB670h2f6rpYS7rnIP/O9CJdPwBWjlejmRQ2RzcIA5ZXx6XhIcP8updtN03IR29q1fhkv594G5FPq+vLaxNl8bl+hkB6H659sO7PiJFRFE3X1wN0gj5QvjjqIh0qiQ2GZ9fwQdB04t89/1O/w1cDnyilFU="
USER_ID = "Ua3cc2b66723eeff4c1e020283b3c0808" 

def is_configured():
    """
    ตรวจสอบว่าได้นำ Token และ User ID มาใส่แทนที่ข้อความ Default หรือยัง
    """
    if CHANNEL_ACCESS_TOKEN.startswith("ใส่_") or USER_ID.startswith("ใส่_"):
        return False
    return True

def send_line_alert(message, to=None):
    """
    ส่งข้อความแจ้งเตือนผ่าน LINE Bot (Push Message)
    """
    if not is_configured():
        print("[LINE Bot Error] ยังไม่ได้ตั้งค่า CHANNEL_ACCESS_TOKEN หรือ USER_ID")
        return False

    # หากมีการระบุผู้รับ (to) ให้ส่งไปที่นั่น ถ้าไม่มีให้ใช้ USER_ID เริ่มต้น
    target_id = to if to else USER_ID
    
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"
    }
    data = {
        "to": target_id,
        "messages": [
            {
                "type": "text",
                "text": message
            }
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        
        # ตรวจสอบสถานะการส่ง (200 คือสำเร็จ)
        if response.status_code == 200:
            print("[LINE Bot] ส่งการแจ้งเตือนสำเร็จ!")
            return True
        else:
            print(f"[LINE Bot Error] ส่งล้มเหลว: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"[LINE Bot Error] เกิดข้อผิดพลาดในการเชื่อมต่อ: {e}")
        return False