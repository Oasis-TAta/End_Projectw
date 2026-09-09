"""ไฟล์นี้ทำหน้าที่เป็น relay service ของ LINE

ภาพรวมการทำงาน:
- รับ request จาก camera.py ผ่าน HTTP POST มาที่ endpoint `/notify`
- ตรวจสอบว่า payload มีข้อความและ target id หรือไม่
- ส่งข้อความต่อไปยัง LINE Messaging API เพื่อ push ข้อความให้ผู้ใช้

พารามิเตอร์ที่จำเป็น:
- LINE_ACCESS_TOKEN: token ของ LINE bot
- LINE_TARGET_ID หรือ LINE_CHAT_TARGET_ID: ผู้รับข้อความ

การไหลของข้อมูล:
- camera.py -> HTTP POST /notify -> line_chat.py -> LINE API -> LINE user/group
"""

# Import ส่วนที่จำเป็น
# Flask: ใช้สร้าง HTTP server และจัดการ endpoint
# os: อ่านค่าตัวแปร environment ที่เก็บ token และ target id
# requests: ใช้ส่ง HTTP request ไปยัง LINE API
from flask import Flask, request, jsonify
import os
import requests

# สร้าง instance ของ Flask application
# ตัวแปรนี้เป็นตัวแทนของ web server ที่จะรอรับ request จาก camera.py
app = Flask(__name__)

# อ่าน token และ target id จาก environment variable
# LINE_ACCESS_TOKEN ต้องมีค่าเสมอ หากไม่มี จะไม่สามารถส่งข้อความไป LINE ได้
# LINE_TARGET_ID หรือ LINE_CHAT_TARGET_ID เป็นค่าที่บอกว่าให้ส่งไปที่ user/group ใด
LINE_TOKEN = os.environ.get("LINE_ACCESS_TOKEN", "")
LINE_TARGET_ID = os.environ.get("LINE_CHAT_TARGET_ID", "") or os.environ.get("LINE_TARGET_ID", "")
LINE_API_URL = "https://api.line.me/v2/bot/message/push"
LINE_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {LINE_TOKEN}",
}

# หากไม่มี LINE_ACCESS_TOKEN ให้หยุดโปรแกรมทันที
# เพราะไม่มี token ไม่สามารถเรียก LINE API ได้
if not LINE_TOKEN:
    raise SystemExit("Missing LINE_ACCESS_TOKEN environment variable. Set it before starting line_chat.py.")


# ฟังก์ชันนี้ทำหน้าที่ส่งข้อความให้ LINE
# Input:
#   to      -> user/group id ที่ต้องการส่งถึง
#   message -> ข้อความที่ต้องการส่ง
# Output:
#   JSON response จาก LINE API

def send_line_push(to, message):
    """ส่งข้อความไปยัง LINE Messaging API แบบ push message."""
    # ถ้า token ว่าง ให้ยก exception ทันที
    if not LINE_TOKEN:
        raise ValueError("LINE_ACCESS_TOKEN is not configured")

    # ถ้าไม่มี target id ให้ยก exception เพราะไม่รู้ว่าจะส่งถึงใคร
    if not to:
        raise ValueError("Target ID is required to send LINE message")

    # สร้าง payload ตามรูปแบบของ LINE Messaging API
    # payload = {
    #   "to": "Uxxxxxxxx",
    #   "messages": [{"type": "text", "text": "hello"}]
    # }
    payload = {
        "to": to,
        "messages": [
            {
                "type": "text",
                "text": message,
            }
        ],
    }

    # ส่ง request แบบ POST ไปที่ LINE API ด้วย Authorization header
    resp = requests.post(LINE_API_URL, json=payload, headers=LINE_HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()


# Endpoint สำหรับรับแจ้งเตือนจาก camera.py
# HTTP method: POST
# ตัวอย่าง request body:
# {
#   "message": "คุณเริ่มนั่งหลังค่อม",
#   "to": "U1234567890"
# }
# หากไม่มี "to" จะใช้ค่า LINE_TARGET_ID จาก environment variable

@app.route("/notify", methods=["POST"])
def notify():
    """จุดรับคำสั่งแจ้งเตือนจาก camera.py"""
    # request.get_json(silent=True) จะพยายามแปลง JSON body ให้เป็น dict
    # ถ้า parse ไม่ได้หรือไม่มีข้อมูล จะคืน None
    data = request.get_json(silent=True)

    # ถ้าไม่มีข้อมูล หรือไม่มี field "message" ให้ตอบกลับ 400
    if not data or "message" not in data:
        return jsonify({"error": "Missing message field"}), 400

    # เลือก target id จาก request body ก่อน จากนั้นค่อยอ่านจาก environment
    to = data.get("to") or LINE_TARGET_ID

    # ถ้ายังไม่มี target id ให้ตอบกลับ 400 เพื่อป้องกันการส่งข้อความผิดคน
    if not to:
        return jsonify({"error": "Missing target id (to)"}), 400

    try:
        # เรียก send_line_push เพื่อส่งข้อความไปยัง LINE
        result = send_line_push(to, data["message"])
        return jsonify({"success": True, "result": result}), 200
    except Exception as exc:
        # หากส่งข้อความล้มเหลว ให้คืน error กลับไปเป็น JSON เพื่อ debug
        return jsonify({"success": False, "error": str(exc)}), 500


# Endpoint สำหรับเช็กว่าบริการยังทำงานอยู่หรือไม่
# ใช้สำหรับ health check หรือการทดสอบเริ่มต้นของ server
@app.route("/healthz", methods=["GET"])
def health():
    """ตรวจสอบสถานะ service ว่ายังทำงานอยู่หรือไม่"""
    return jsonify({"status": "ok"}), 200


# ส่วนนี้ทำงานเฉพาะเมื่อรันไฟล์นี้ตรง ๆ ด้วย `python line_chat.py`
# ถ้า import file นี้ไปใช้ในไฟล์อื่น จะไม่รัน server ขึ้นมาเอง
if __name__ == "__main__":
    # อ่าน host และ port จาก environment variable
    # ค่าเริ่มต้น: host = 0.0.0.0 (รับ request จากทุก interface)
    # port = 5000
    host = os.environ.get("LINE_CHAT_HOST", "0.0.0.0")
    port = int(os.environ.get("LINE_CHAT_PORT", 5000))

    # แสดงข้อความให้เห็นว่า service กำลังเริ่มต้น
    print(f"Starting line_chat service on {host}:{port}")

    # เรียก app.run เพื่อเปิด Flask server จริง
    app.run(host=host, port=port)
