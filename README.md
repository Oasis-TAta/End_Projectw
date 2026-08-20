# End_Project

โปรเจกต์นี้เป็นระบบตรวจจับท่าทางการนั่ง (posture detection) พร้อมฟีเจอร์แจ้งเตือนผ่าน LINE
โดยประกอบด้วยไฟล์หลัก 3 ตัว:

- `camera.py` - อ่านภาพจากกล้อง, วิเคราะห์ท่าทางด้วย MediaPipe,
  และส่งคำสั่งแจ้งเตือนไปยังบริการ relay ของ LINE
- `line_chat.py` - เป็น Flask service ที่รับคำสั่งจาก `camera.py`
  และส่งข้อความไปยัง LINE Messaging API
- `main.py` - รันทั้ง `line_chat.py` และ `camera.py` พร้อมกันด้วยคำสั่งเดียว

## การทำงานโดยสรุป

1. `main.py` จะสตาร์ท `line_chat.py` ใน background thread
   - ทำให้เกิดบริการ HTTP ภายในเครื่อง
   - บริการนี้เปิด endpoint `/notify` เพื่อรอรับคำสั่งแจ้งเตือน

2. `main.py` จะสตาร์ท `camera.py` ใน main thread
   - `camera.py` จะเปิดกล้องและเรียกใช้ MediaPipe วิเคราะห์ท่าทาง
   - คำนวณมุมกระดูกสันหลัง (spine angle) และความยื่นของศีรษะ
   - หากตรวจพบท่าทางไม่ดีต่อเนื่อง จะส่ง POST ไปยัง `line_chat.py`

3. `line_chat.py` จะส่งข้อความไปยัง LINE
   - ใช้ค่า `LINE_ACCESS_TOKEN`
   - ใช้ค่า `LINE_TARGET_ID` หรือ `LINE_CHAT_TARGET_ID`
   - ส่งข้อความเป็น plain text ผ่าน LINE Messaging API

## ขั้นตอนการติดตั้ง

ติดตั้ง dependencies:

```powershell
pip install flask requests opencv-python mediapipe
```

ตั้งค่าตัวแปรสภาพแวดล้อม:

```powershell
set LINE_ACCESS_TOKEN=<LINE channel access token>
set LINE_TARGET_ID=<LINE user or group id>
set LINE_CHAT_HOST=http://127.0.0.1:5000
```

## วิธีรัน

รันคำสั่งเดียวเพื่อเปิดทั้งสองส่วน:

```powershell
python main.py
```

## ข้อควรระวัง

- `main.py` จะรัน `line_chat.py` ก่อน แล้วรอ 1 วินาที ก่อนรัน `camera.py`
- หาก `line_chat.py` ใช้เวลานานกว่า 1 วินาทีในการเปิดให้บริการ
  ให้ปรับค่า `time.sleep(1)` ใน `main.py`
- `camera.py` จะส่งคำสั่งแจ้งเตือนใน background thread
  เพื่อไม่ให้ลูปกล้องถูกบล็อก
- `line_chat.py` ส่งข้อความ LINE เป็นข้อความตัวอักษรธรรมดาเท่านั้น

## รูปแบบการใช้งาน Git

```powershell
git add .
git commit -m "Save progress"
git pull origin main --rebase
git push
```
