import requests

# ============================================================================
# ตั้งค่า LINE Notify Token
# สามารถออก Token ฟรีได้ที่: https://notify-bot.line.me/my/
# ============================================================================
LINE_NOTIFY_TOKEN = "ใส่_TOKEN_ของคุณที่นี่"

def is_configured():
    """
    ตรวจสอบว่าได้นำ Token มาใส่แทนที่ข้อความ Default หรือยัง
    """
    if LINE_NOTIFY_TOKEN == "ใส่_TOKEN_ของคุณที่นี่" or not LINE_NOTIFY_TOKEN.strip():
        return False
    return True

def send_line_alert(message, to=None):
    """
    ส่งข้อความแจ้งเตือนไปยัง LINE
    """
    if not is_configured():
        print("[LINE Error] ไม่สามารถส่งข้อความได้ เนื่องจากยังไม่ได้ตั้งค่า LINE_NOTIFY_TOKEN")
        return False

    url = "https://notify-api.line.me/api/notify"
    headers = {
        "Authorization": f"Bearer {LINE_NOTIFY_TOKEN}"
    }
    data = {
        "message": message
    }

    try:
        response = requests.post(url, headers=headers, data=data)
        
        # ตรวจสอบว่าส่งสำเร็จหรือไม่ (Status Code 200 คือสำเร็จ)
        if response.status_code == 200:
            print("[LINE] ส่งการแจ้งเตือนสำเร็จ!")
            return True
        else:
            print(f"[LINE Error] ส่งล้มเหลว: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"[LINE Error] เกิดข้อผิดพลาดในการเชื่อมต่อ: {e}")
        return False