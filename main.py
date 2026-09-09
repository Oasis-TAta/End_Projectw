<<<<<<< HEAD
import camera

if __name__ == "__main__":
    print("[System] กำลังเริ่มต้นระบบ Posture Guard และเปิดกล้อง...")
    
    # เช็คว่าในไฟล์ camera.py มีฟังก์ชัน main() หรือรันโดยอัตโนมัติ
    if hasattr(camera, 'main'):
        camera.main()
    elif hasattr(camera, 'run'):
        camera.run()
=======
"""ไฟล์นี้เป็นตัวเรียกใช้งานหลักของโปรเจกต์

จุดประสงค์:
1) เริ่มบริการ Flask จาก line_chat.py เพื่อรอรับข้อมูลแจ้งเตือน
2) เริ่มโปรแกรมตรวจจับท่าทางจาก camera.py
3) รันทั้งสองส่วนพร้อมกันด้วยคำสั่งเดียว

การทำงานแบบไหลของข้อมูล:
- `main.py` อ่านค่า environment variables เช่น LINE_ACCESS_TOKEN
- `main.py` เรียก `line_chat.py` ขึ้นมาทำงานใน background thread
- หลังจากนั้น `main.py` จะ import `camera.py`
- `camera.py` จะเปิดกล้องและตรวจจับท่าทาง
- เมื่อพบว่าท่าทางไม่ดี จะส่ง HTTP POST ไปยัง `line_chat.py`
- `line_chat.py` จะส่งข้อความต่อไปยัง LINE Messaging API

วิธีรัน:
  set LINE_ACCESS_TOKEN=<ค่า token ของ LINE bot>
  set LINE_TARGET_ID=<หมายเลขผู้รับข้อความ>
  set LINE_CHAT_HOST=http://127.0.0.1:5000
  python main.py
"""

# Import ส่วนที่จำเป็นสำหรับโปรแกรม
# os: ใช้อ่านค่า environment variables และข้อมูลต่าง ๆ จากระบบ
# threading: ใช้สร้างเธรด (background thread) ให้ line_chat ทำงานแยกจาก main program
# time: ใช้หยุดให้บริการเริ่มต้นก่อน camera.py ทำงาน
import os
import threading
import time
from urllib.parse import urlparse


# ฟังก์ชันนี้เป็นตัวเริ่ม Flask service จากไฟล์ line_chat.py
# โดยจะทำงานแบบ background thread เพื่อไม่ให้โปรแกรมหลักถูกบล็อก
# เนื่องจาก camera.py เป็นลูปภาพถ่ายจากกล้อง จึงควรให้ line_chat วิ่งแยกไว้ก่อน
# แล้วค่อยให้ camera.py เริ่มทำงานต่อ

def run_line_chat():
    """เริ่ม Flask service ของ line_chat.py ใน background thread"""
    # Import `app` จาก line_chat.py ภายในฟังก์ชันนี้เพื่อให้ค่า environment ถูกตั้งไว้ก่อน
    # ถ้า import ข้างนอกแล้วอาจยังไม่มี LINE_ACCESS_TOKEN หรือ LINE_TARGET_ID
    from line_chat import app

    # อ่าน host และ port จาก environment variable
    # รองรับทั้ง `127.0.0.1` และ URL เช่น `http://127.0.0.1:5000`
    configured_host = os.environ.get("LINE_CHAT_HOST", "127.0.0.1")
    parsed_host = urlparse(configured_host if "://" in configured_host else f"//{configured_host}")
    host = parsed_host.hostname or "127.0.0.1"
    port = int(os.environ.get("LINE_CHAT_PORT", parsed_host.port or 5000))

    # แสดงข้อความตอนเริ่มต้นเพื่อตรวจสอบว่า service เริ่มทำงานแล้วหรือยัง
    print(f"Starting line_chat service on {host}:{port}...")

    # เรียก app.run เพื่อเปิด Flask server
    # threaded=True อนุญาตให้รับ request พร้อมกันหลาย request
    # use_reloader=False ปิดโหมด auto-reload เพื่อป้องกันการเริ่มโปรแกรมซ้ำซ้อน
    app.run(host=host, port=port, threaded=True, use_reloader=False)


# ฟังก์ชัน main เป็นจุดเริ่มของโปรแกรมทั้งหมด
# จะทำงานตามลำดับดังนี้:
# 1) เปิด line_chat service ใน background thread
# 2) รอ 1 วินาทีเพื่อให้ server พร้อมรับ request
# 3) import camera.py และเริ่มการตรวจจับท่าทาง

def main():
    """เริ่ม line_chat ก่อน แล้วตามด้วย camera.py"""
    # สร้าง thread ใหม่ เพื่อให้ line_chat ทำงานแบบแยกจาก thread หลัก
    # daemon=True หมายถึงเมื่อโปรแกรมหลักปิด Thread นี้จะปิดตามไปด้วย
    thread = threading.Thread(target=run_line_chat, daemon=True)
    thread.start()

    # หยุด 1 วินาทีเพื่อให้ Flask service มีเวลาสำหรับเริ่มเปิด port
    # ถ้าคุณใช้เครื่องช้าหรือระบบช้า อาจต้องปรับค่าให้มากขึ้น เช่น 2 หรือ 3
    time.sleep(1)

    print("Starting camera posture detector...")

    # import camera เป็นการเริ่มต้นประมวลผลกล้องและ pose detection
    # เมื่อ import module แล้ว มันจะเริ่มทำงานทันที เพราะมีโค้ดหลักอยู่ภายใต้ if __name__ == "__main__"
    # แต่ในไฟล์นี้เรา import camera เพื่อให้มันเริ่มทำงานทันทีภายใน same process
    import camera  # noqa: F401


# เงื่อนไขนี้ทำให้โปรแกรมเริ่มทำงานเฉพาะตอนรันผ่าน `python main.py`
# ถ้า import main.py ไปใช้ในไฟล์อื่น จะไม่ทำงานทันที
if __name__ == "__main__":
    main()
>>>>>>> 689ba237a81ae221eb85d2c256bc98b989dd3b12
