
# ==========================
# นำเข้า (import) ไลบรารีที่ต้องใช้
# ==========================

# Flask ใช้เปิดเซิร์ฟเวอร์เล็ก ๆ เพื่อรับข้อความจาก LINE
from flask import Flask, request

# WebhookHandler ใช้รับข้อมูลที่ LINE ส่งเข้ามา
from linebot.v3 import WebhookHandler

# ชุดเครื่องมือสำหรับตอบข้อความกลับ LINE
from linebot.v3.messaging import (
    Configuration,         # เก็บ token ของ LINE
    ApiClient,             # ใช้เชื่อมกับ LINE API
    MessagingApi,          # ใช้ส่งข้อความ
    ReplyMessageRequest,   # รูปแบบการตอบกลับ
    TextMessage            # ข้อความแบบตัวหนังสือ
)

# ใช้จัดการประเภทข้อความที่ส่งเข้ามา
from linebot.v3.webhooks import (
    MessageEvent,          # Event เมื่อมีข้อความเข้า
    TextMessageContent     # ข้อความประเภท text
)

# ใช้ตรวจสอบว่า request มาจาก LINE จริงไหม
from linebot.exceptions import InvalidSignatureError


# ==========================
# สร้าง Flask App
# ==========================

# app คือเซิร์ฟเวอร์ของเรา
app = Flask(__name__)


# ==========================
# ใส่ข้อมูลของ LINE Bot
# ==========================

# ใส่ Channel Access Token ของนาย
# หาได้จาก LINE Developers > Messaging API > Channel access token
CHANNEL_ACCESS_TOKEN = "ใส่ token ของนายตรงนี้"

# ใส่ Channel Secret ของนาย
# หาได้จาก Basic Settings > Channel Secret
CHANNEL_SECRET = "ใส่ channel secret ตรงนี้"


# ==========================
# ตั้งค่า LINE Configuration
# ==========================

# เอา token ไปตั้งค่าให้ระบบ LINE
configuration = Configuration(
    access_token=CHANNEL_ACCESS_TOKEN
)

# สร้าง handler สำหรับจัดการ webhook
handler = WebhookHandler(CHANNEL_SECRET)


# ==========================
# Route สำหรับรับข้อมูลจาก LINE
# ==========================

# LINE จะส่งข้อมูลมาที่ /callback
@app.route("/callback", methods=["POST"])
def callback():

    # รับ Signature จาก LINE
    # ใช้ยืนยันว่า request มาจาก LINE จริง
    signature = request.headers["X-Line-Signature"]

    # รับข้อมูลข้อความทั้งหมด
    body = request.get_data(as_text=True)

    try:
        # ส่งข้อมูลให้ handler ประมวลผล
        handler.handle(body, signature)

    except InvalidSignatureError:
        # ถ้า signature ไม่ถูกต้อง
        return "Invalid signature", 400

    # ถ้าปกติให้ตอบ OK
    return "OK"


# ==========================
# ฟังก์ชันตอบข้อความ
# ==========================

# เมื่อมีข้อความเข้ามา
@handler.add(MessageEvent)
def handle_message(event):

    # เช็กว่าเป็นข้อความ text หรือไม่
    if isinstance(event.message, TextMessageContent):

        # ดึงข้อความของผู้ใช้
        text = event.message.text.lower()

        # ==========================
        # ระบบคีย์เวิร์ด
        # ==========================

        # ถ้าผู้ใช้พิมพ์ "เมนู"
        if text == "เมนู":

            # ข้อความที่จะตอบกลับ
            reply = (
                "📚 เมนู\n"
                "1.คะแนน\n"
                "2.ตารางเรียน"
            )

        # ถ้าพิมพ์ "คะแนน"
        elif text == "คะแนน":

            reply = "คะแนนของคุณคือ 95"

        # ถ้าพิมพ์ "ตารางเรียน"
        elif text == "ตารางเรียน":

            reply = "วันนี้มี วิทย์ คณิต อังกฤษ"

        # ถ้าไม่ตรงกับคีย์เวิร์ดไหน
        else:

            reply = "ไม่เข้าใจคำสั่ง"

        # ==========================
        # ส่งข้อความกลับไปที่ LINE
        # ==========================

        # เปิดการเชื่อมต่อ LINE API
        with ApiClient(configuration) as api_client:

            # สร้างตัวส่งข้อความ
            line_bot_api = MessagingApi(api_client)

            # ตอบกลับข้อความ
            line_bot_api.reply_message(

                # รูปแบบข้อความตอบกลับ
                ReplyMessageRequest(

                    # token สำหรับตอบกลับข้อความนั้น
                    reply_token=event.reply_token,

                    # รายการข้อความที่จะส่ง
                    messages=[

                        # ส่งข้อความแบบ text
                        TextMessage(
                            text=reply
                        )
                    ]
                )
            )


# ==========================
# เริ่มรันเซิร์ฟเวอร์
# ==========================

# ถ้าเปิดไฟล์นี้โดยตรง
if __name__ == "__main__":

# เปิด server ที่ port 5000
  app.run(port=5000) 
