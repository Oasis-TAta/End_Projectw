# End_Project

โปรเจกต์นี้มีวัตถุประสงค์เพื่อจับท่าทางการนั่งและส่งคำเตือนผ่าน LINE เมื่อพบว่าผู้ใช้กำลังนั่งหลังค่อม หรือศีรษะคอยื่นผิดรูปแบบเกินขีดที่ตั้งไว้

## ภาพรวมของโปรเจกต์

โปรเจกต์นี้ประกอบด้วยไฟล์หลัก 3 ไฟล์:

1. `camera.py`
   - ทำหน้าที่เปิดกล้องและตรวจจับ landmark ของร่างกายด้วย MediaPipe
   - คำนวณมุมกระดูกสันหลังและการเอียงของศีรษะ
   - ถ้าตรวจพบว่าท่าทางไม่ดีต่อเนื่อง จะส่งข้อมูลไปยัง `line_chat.py`

2. `line_chat.py`
   - ทำหน้าที่เป็น relay service
   - รับ HTTP request จาก `camera.py`
   - ส่งข้อความไปยัง LINE Messaging API

3. `main.py`
   - เป็นไฟล์รันหลัก
   - เรียกใช้งาน `line_chat.py` และ `camera.py` พร้อมกันด้วยคำสั่งเดียว

## การทำงานของระบบแบบสั้น ๆ

1. `main.py` เริ่ม Web API จาก `line_chat.py`
2. `camera.py` เปิดกล้องและเริ่มวิเคราะห์ท่าทาง
3. ระบบคำนวณค่าทางคณิตศาสตร์ เช่น มุมหลังและระยะคอยื่นของศีรษะ
4. ถ้าท่านั่งไม่ดีเกินเกณฑ์ จะสร้างข้อความเตือน
5. ข้อความถูกส่งไปที่ `line_chat.py`
6. `line_chat.py` ส่ง push notification ไปยัง LINE Bot

## โครงสร้างข้อมูลที่ไหลผ่านระบบ

```text
กล้อง หรือ webcam
      ↓
camera.py
      ↓
ตรวจจับ landmark / พิกัด / มุม
      ↓
เช็คเกณฑ์ท่าทางไม่ดี
      ↓
HTTP POST /notify
      ↓
line_chat.py
      ↓
LINE Messaging API
      ↓
LINE User / LINE Group
```

## สิ่งที่ต้องติดตั้งก่อนรัน

ใช้คำสั่งต่อไปนี้ใน terminal:

```powershell
pip install flask requests opencv-python mediapipe
```

หากต้องการรันในระบบ Windows PowerShell สามารถใช้คำสั่งดังนี้:

```powershell
set LINE_ACCESS_TOKEN=<LINE channel access token>
set LINE_TARGET_ID=<user or group id>
set LINE_CHAT_HOST=http://127.0.0.1:5000
python main.py
```

## การตั้งค่า environment variables

- `LINE_ACCESS_TOKEN`
  - เป็น token ที่ได้จาก LINE Developer Console
  - ใช้สำหรับ authenticating กับ LINE Messaging API

- `LINE_TARGET_ID`
  - เป็น id ของผู้ใช้หรือกลุ่มที่ต้องการให้ส่งข้อความถึง

- `LINE_CHAT_HOST`
  - เป็น URL ของ server ที่ `line_chat.py` เปิดอยู่
  - ค่าเริ่มต้นคือ `http://127.0.0.1:5000`

- `CAMERA_INDEX`
      - หมายเลขกล้องที่ต้องการใช้
      - ค่าเริ่มต้นคือ `0`

- `CAMERA_WIDTH` และ `CAMERA_HEIGHT`
      - ความละเอียดภาพจากกล้อง
      - ค่าเริ่มต้นคือ `640x480`
      - ระบบจำกัดค่าสูงสุดไว้ที่ `1280x700` เสมอ

## การจับเวลาและแจ้งเตือน LINE

- ระบบเริ่มจับเวลาเมื่อพบว่าท่านั่งผิด
- เมื่อท่าผิดต่อเนื่องเกิน 10 วินาที จะส่งการแจ้งเตือนไปยัง `line_chat.py`
- `line_chat.py` จะส่งข้อความต่อไปยัง LINE Bot
- ในเวลาเดียวกัน `camera.py` จะแสดงข้อความ `[POSTURE ALERT]` ใน terminal
      ที่ใช้รัน `python main.py`
- เมื่อท่ากลับมาถูก ระบบจะหยุดและรีเซ็ต timer ทันที
- หากยังนั่งผิดต่อ จะส่งซ้ำได้หลัง cooldown 300 วินาที เพื่อป้องกันข้อความถี่เกินไป

## การตั้งค่าสำหรับ Raspberry Pi 4GB

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install flask requests opencv-python mediapipe

export LINE_ACCESS_TOKEN="ใส่_CHANNEL_ACCESS_TOKEN ที่นี่"
export LINE_TARGET_ID="ใส่_USER_ID หรือ GROUP_ID ที่นี่"
export LINE_CHAT_HOST="http://127.0.0.1:5000"
export CAMERA_INDEX="0"
export CAMERA_WIDTH="640"
export CAMERA_HEIGHT="480"
python main.py
```

หากต้องการใช้ความละเอียดสูงขึ้น สามารถตั้งได้ไม่เกิน 1280x700:

```bash
export CAMERA_WIDTH="1280"
export CAMERA_HEIGHT="700"
python main.py
```

## การรันโปรแกรม

คำสั่งเดียวที่ใช้คือ:

```powershell
python main.py
```

เมื่อรันแล้วจะเกิดสิ่งต่อไปนี้:

- `line_chat.py` จะเริ่มทำงานหน้า background
- `camera.py` จะเปิดกล้องทันที
- หาก TUI/หน้าจอแสดงผลมีปัญหา หรือท่าทางไม่ดี
  จะมีข้อความเตือนปรากฏบนหน้าจอและรวมถึงส่งไปทาง LINE

## ข้อควรระวัง

- `main.py` ให้ `line_chat.py` เริ่มก่อน 1 วินาที เพื่อให้ server พร้อมรับ request
- หาก server เริ่มช้ากว่า 1 วินาที ให้เพิ่ม `time.sleep(1)` เป็น 2 หรือ 3
- `line_chat.py` ส่งได้เฉพาะข้อความข้อความธรรมดา (text message)
- ถ้าลองใช้เครื่องที่ไม่มีกล้อง หรือ token ไม่ถูกต้อง การทำงานจะผิดพลาด
- การส่ง LINE จริงต้องมีอินเทอร์เน็ตและค่า token/target id ที่ถูกต้อง

## การแก้ไขต่อไปที่เหมาะสม

ถ้าจะต่อยอดในอนาคต ควรเริ่มจากส่วนต่อไปนี้:

- ปรับเกณฑ์ `SPINE_ANGLE_GOOD` และ `SPINE_ANGLE_WARN` ใน `camera.py`
- ปรับข้อความเตือนให้ตรงกับพฤติกรรมผู้ใช้
- เพิ่มการบันทึก log ลงไฟล์เพื่อดูประวัติการแจ้งเตือน
- เพิ่มการคัดกรองว่าเปิดกล้องระยะยาวหรือไม่
- เพิ่ม endpoint สำหรับรับข้อความหลายประเภท เช่น image, sticker, template message

## Git workflow

```powershell
git add .
git commit -m "Save progress"
git pull origin main --rebase
git push
```
