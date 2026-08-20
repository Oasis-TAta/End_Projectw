from flask import Flask, request, jsonify
import os
import requests

# สร้าง Flask application เล็ก ๆ สำหรับเป็น service รอรับคำสั่งจาก camera.py
# และส่งข้อความต่อไปยัง LINE Messaging API
#
# วิธีใช้งาน:
# 1) ตั้งค่า environment variables:
#    LINE_ACCESS_TOKEN = <LINE channel access token>
#    LINE_TARGET_ID or LINE_CHAT_TARGET_ID = <recipient user/group ID>
#    LINE_CHAT_HOST = http://127.0.0.1:5000  # optional
#    LINE_CHAT_PORT = 5000                  # optional
# 2) รัน service: python line_chat.py
# 3) ทดสอบจาก camera.py หรือด้วย curl/postman
app = Flask(__name__)

# อ่านค่า LINE token จาก environment variable
# ต้องตั้งค่า LINE_ACCESS_TOKEN ให้เป็น Channel access token ของ LINE Bot
LINE_TOKEN = os.environ.get("LINE_ACCESS_TOKEN", "")
LINE_TARGET_ID = os.environ.get("LINE_CHAT_TARGET_ID", "") or os.environ.get("LINE_TARGET_ID", "")
LINE_API_URL = "https://api.line.me/v2/bot/message/push"
LINE_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {LINE_TOKEN}",
}

if not LINE_TOKEN:
    raise SystemExit("Missing LINE_ACCESS_TOKEN environment variable. Set it before starting line_chat.py.")


def send_line_push(to, message):
    """ส่งข้อความไปยัง LINE Messaging API แบบ push message."""
    if not LINE_TOKEN:
        raise ValueError("LINE_ACCESS_TOKEN is not configured")

    # สร้าง payload ตาม API ของ LINE messaging
    payload = {
        "to": to,
        "messages": [
            {
                "type": "text",
                "text": message,
            }
        ],
    }

    # เรียก HTTP POST ไปยัง LINE API
    resp = requests.post(LINE_API_URL, json=payload, headers=LINE_HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()


@app.route("/notify", methods=["POST"])
def notify():
    """จุดรับคำสั่งแจ้งเตือนจาก camera.py.

    body ต้องเป็น JSON และต้องมี field 'message'.
    field 'to' เป็น optional; ถ้าไม่มีจะอ่านจาก LINE_TARGET_ID ใน environment.
    """
    data = request.get_json(silent=True)
    if not data or "message" not in data:
        return jsonify({"error": "Missing message field"}), 400

    # กำหนด target id จาก request หรือ environment variable
    to = data.get("to") or LINE_TARGET_ID
    if not to:
        return jsonify({"error": "Missing target id (to)"}), 400

    try:
        result = send_line_push(to, data["message"])
        return jsonify({"success": True, "result": result}), 200
    except Exception as exc:
        # ถ้ามีปัญหาเรียก LINE API ให้คืน error กลับไป
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/healthz", methods=["GET"])
def health():
    """ตรวจสอบสถานะ service ว่ายังทำงานอยู่หรือไม่"""
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    # ตั้งค่า host/port สำหรับรัน Flask service
    host = os.environ.get("LINE_CHAT_HOST", "0.0.0.0")
    port = int(os.environ.get("LINE_CHAT_PORT", 5000))
    print(f"Starting line_chat service on {host}:{port}")
    app.run(host=host, port=port)
