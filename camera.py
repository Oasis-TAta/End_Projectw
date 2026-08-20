# ============================================================================
# Posture Guard — ตรวจจับการนั่งหลังค่อม ป้องกัน Office Syndrome
# ใช้ MediaPipe Pose Tasks API (v0.10+)
#
# ติดตั้ง: pip install opencv-python mediapipe requests
# รันด้วย:  python posture_guard.py
#
# ครั้งแรกจะดาวน์โหลดโมเดล pose_landmarker_lite.task (~28MB) อัตโนมัติ
#
# Landmark ที่ใช้:
#   0  = nose         (จมูก)
#   7  = left_ear      (หูซ้าย)
#   8  = right_ear     (หูขวา)
#   11 = left_shoulder
#   12 = right_shoulder
#   23 = left_hip
#   24 = right_hip
#
# แก้ไข: เชื่อมต่อกับ line_chat.py service เพื่อส่งข้อความแจ้งเตือนเข้า LINE
#         ในเวอร์ชันนี้ camera.py จะ POST ข้อความไปยัง Flask service
#         ส่วน line_chat.py จะเป็น service ที่รับคำสั่งและเรียก LINE Messaging API
# แก้ไข: เพิ่มจุดข้อต่อกระดูกสันหลังแบบเส้นโค้ง (Catmull-Rom spline) ละเอียดขึ้นมาก
# แก้ไข: แยกค่าตั้งเวลาแจ้งเตือนออกเป็น "โซน" ชัดเจน คอมเมนต์ทั้งบล็อกได้ง่าย
# ============================================================================

import cv2                                              # ใช้วาดภาพ/แสดงผลกล้อง (OpenCV)
import math                                             # ใช้คำนวณมุมและระยะทาง (acos, hypot)
import time                                              # ใช้จับเวลา session และ cooldown ของการแจ้งเตือน
import threading                                        # แก้ไข: ใช้รันการส่ง LINE แบบ background ไม่ให้ภาพกระตุก
import urllib.request                                    # ใช้ดาวน์โหลดโมเดล pose จากอินเทอร์เน็ต
import os                                                # ใช้เช็คว่าไฟล์โมเดลมีอยู่แล้วหรือยัง
try:
    import requests                                    # ใช้ส่ง POST ไปยัง line_chat service
except ImportError:
    requests = None
import mediapipe as mp                                   # ไลบรารีตรวจจับท่าทางร่างกาย (Pose Landmarker)
from mediapipe.tasks import python as mp_python           # โมดูลย่อยสำหรับตั้งค่า BaseOptions ของโมเดล
from mediapipe.tasks.python import vision as mp_vision    # โมดูลย่อยสำหรับ PoseLandmarker (vision tasks)
from mediapipe.tasks.python.vision import PoseLandmarksConnections  # เส้นเชื่อมจุด landmark มาตรฐานของ MediaPipe

# LINE chat relay service configuration
# camera.py จะส่ง POST ไปยัง service ที่รันโดย line_chat.py
# โดยค่าเริ่มต้นจะเป็น http://127.0.0.1:5000/notify
LINE_CHAT_HOST = os.environ.get("LINE_CHAT_HOST", "http://127.0.0.1:5000")
LINE_CHAT_NOTIFY_URL = f"{LINE_CHAT_HOST.rstrip('/')}/notify"
LINE_CHAT_DEFAULT_TO = os.environ.get("LINE_CHAT_TARGET_ID", os.environ.get("LINE_TARGET_ID", ""))  # LINE user/group ID to push messages to
LINE_MODULE_AVAILABLE = requests is not None                        # มีไลบรารี requests อยู่หรือไม่


def send_line_alert(message, to=None):                              # ส่งข้อความไปที่ line_chat service
    """ส่งคำสั่งแจ้งเตือนไปยัง line_chat service แบบ HTTP POST."""
    if requests is None:                                              # ถ้าไม่มี requests ให้ข้ามการส่ง
        return False
    payload = {"message": message}
    if to:
        payload["to"] = to
    elif LINE_CHAT_DEFAULT_TO:
        payload["to"] = LINE_CHAT_DEFAULT_TO

    # เรียก POST ไปยัง line_chat service ที่รอรับคำสั่ง
    try:
        resp = requests.post(LINE_CHAT_NOTIFY_URL, json=payload, timeout=3)
        resp.raise_for_status()
        return True
    except Exception as exc:
        print(f"[LINE_CHAT] failed to send alert: {exc}")
        return False


def line_is_configured():
    """ตรวจสอบว่าสามารถส่งข้อความผ่าน line_chat service ได้หรือไม่."""
    return LINE_MODULE_AVAILABLE and bool(LINE_CHAT_DEFAULT_TO)

# ==================== ดาวน์โหลดโมเดล ====================
MODEL_PATH = "pose_landmarker_lite.task"                  # ชื่อไฟล์โมเดลที่จะเก็บไว้ในเครื่อง
MODEL_URL  = (                                             # URL ต้นทางของโมเดล (Google Cloud Storage)
    "https://storage.googleapis.com/mediapipe-models/"     # ส่วนโดเมนของ URL
    "pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"  # ส่วน path ของไฟล์โมเดล
)
if not os.path.exists(MODEL_PATH):                         # ถ้ายังไม่มีไฟล์โมเดลในเครื่อง
    print("กำลังดาวน์โหลดโมเดล pose (~28MB) ...")            # แจ้งผู้ใช้ว่ากำลังดาวน์โหลด
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)       # ดาวน์โหลดไฟล์โมเดลมาเก็บไว้
    print("ดาวน์โหลดสำเร็จ!")                                # แจ้งผู้ใช้ว่าดาวน์โหลดเสร็จแล้ว

# ==================== Landmark index ====================
NOSE           = 0                                          # index ของจุดจมูกใน pose landmark
LEFT_EAR       = 7                                          # index ของจุดหูซ้าย
RIGHT_EAR      = 8                                          # index ของจุดหูขวา
LEFT_SHOULDER  = 11                                         # index ของจุดไหล่ซ้าย
RIGHT_SHOULDER = 12                                         # index ของจุดไหล่ขวา
LEFT_HIP       = 23                                         # index ของจุดสะโพกซ้าย
RIGHT_HIP      = 24                                         # index ของจุดสะโพกขวา

CONNECTIONS = PoseLandmarksConnections.POSE_LANDMARKS        # เส้นเชื่อมจุด landmark ทั้งหมดของ MediaPipe (โครงกระดูกเต็มตัว)


# ============================================================================
# 🟦 ZONE 1: เกณฑ์ตรวจจับท่าทาง (POSTURE DETECTION THRESHOLDS)
#     - ปรับค่าตรงนี้เพื่อเปลี่ยนความไวในการตรวจจับว่า "ค่อม" หรือ "คอยื่น"
#     - คอมเมนต์ทั้งบล็อกนี้ไม่ได้ เพราะโค้ดส่วนวิเคราะห์ท่าทางต้องใช้ค่าเหล่านี้เสมอ
#       แต่ปรับตัวเลขแต่ละบรรทัดเพื่อ tune ความไวได้อิสระ
# ============================================================================
SPINE_ANGLE_GOOD  = 160     # องศา: มุมหู-ไหล่-สะโพก ถ้ามากกว่านี้ถือว่า "ท่าดี"
SPINE_ANGLE_WARN  = 145     # องศา: ถ้ามุมต่ำกว่านี้ถือว่า "ค่อมชัดเจน" (ระหว่าง WARN-GOOD คือ "เริ่มค่อม")
HEAD_FORWARD_THRESH = 0.06  # หน่วย normalized (0-1): ระยะหูเยื้องจากไหล่แนวนอน ถ้ามากกว่านี้ถือว่า "คอยื่น"


# ============================================================================
# 🟨 ZONE 2: เวลาแจ้งเตือนบนหน้าจอ (ON-SCREEN ALERT TIMING)
#     - คุมว่ากล่องข้อความเตือนสีน้ำเงินด้านล่างจอจะขึ้นเมื่อไหร่/นานแค่ไหน
#     - ถ้าอยากปิดการเตือนบนจอทั้งหมด ให้คอมเมนต์ 3 บรรทัดค่านี้ทิ้ง แล้วตั้งค่า
#       BAD_DURATION_TRIGGER = 999999 แทน (ค่อมนานขนาดนั้นแทบไม่มีทางเกิดขึ้น)
# ============================================================================
BAD_DURATION_TRIGGER = 3    # วินาที: ต้องค่อม/คอยื่นต่อเนื่องกี่วินาทีก่อนขึ้นกล่องเตือนบนจอ
ALERT_COOLDOWN_SEC   = 8    # วินาที: หลังเตือนบนจอไปแล้ว ต้องรอกี่วินาทีถึงจะเตือนซ้ำได้
ALERT_DISPLAY_SEC    = 5    # วินาที: กล่องเตือนบนจอค้างอยู่นานกี่วินาทีต่อครั้งก่อนหาย


# ============================================================================
# 🟥 ZONE 3: เวลาแจ้งเตือนเข้า LINE (LINE ALERT TIMING)
#     - แยกออกจาก ZONE 2 โดยตั้งใจ เพราะอยากให้ LINE เตือน "นานกว่า" การเตือนบนจอ
#       (กันสแปมมือถือทุกครั้งที่ก้มนิดเดียว)
#     - ถ้าไม่อยากให้ส่ง LINE เลย คอมเมนต์บล็อกนี้ทั้งหมด แล้วตั้ง
#       LINE_ALERT_DURATION_TRIGGER = 999999 แทนได้เลย (หรือลบไฟล์ line_notify.py ทิ้ง)
# ============================================================================
LINE_ALERT_DURATION_TRIGGER = 60    # วินาที: ต้องค่อมต่อเนื่องนานเท่านี้ก่อนยิงข้อความไป LINE
LINE_ALERT_COOLDOWN_SEC     = 300   # วินาที: ส่ง LINE ซ้ำได้ทุกกี่วินาที (300 = 5 นาที) กันสแปม


# ==================== ฟังก์ชันช่วย ====================
def angle_3pts(a, b, c):                                    # ฟังก์ชันคำนวณมุม ABC จาก 3 จุด (x, y)
    """คำนวณมุม ABC (หน่วย องศา) จาก 3 จุด (x, y)"""          # คำอธิบาย docstring ของฟังก์ชัน
    ax, ay = a[0]-b[0], a[1]-b[1]                             # เวกเตอร์จาก B ไป A (แกน x, y)
    cx, cy = c[0]-b[0], c[1]-b[1]                             # เวกเตอร์จาก B ไป C (แกน x, y)
    dot   = ax*cx + ay*cy                                     # ผลคูณจุด (dot product) ของสองเวกเตอร์
    mag_a = math.hypot(ax, ay)                                 # ความยาวเวกเตอร์ B->A
    mag_c = math.hypot(cx, cy)                                 # ความยาวเวกเตอร์ B->C
    if mag_a * mag_c == 0:                                     # กันหารด้วยศูนย์ (จุดซ้อนทับกัน)
        return 180.0                                            # คืนมุม 180 องศา (ถือว่าตรง) เป็นค่า fallback
    return math.degrees(math.acos(max(-1, min(1, dot / (mag_a * mag_c)))))  # คำนวณมุมจาก cos แล้วแปลงเป็นองศา


def midpoint(a, b):                                           # ฟังก์ชันหาจุดกึ่งกลางระหว่างสองจุด
    return ((a[0]+b[0])//2, (a[1]+b[1])//2)                    # คืนค่าพิกัด (x, y) กึ่งกลางแบบ integer


def lerp_point(a, b, t):                                       # ฟังก์ชันสอดแทรกจุดเชิงเส้น (linear interpolation)
    """สอดแทรกจุดระหว่าง a กับ b ตามสัดส่วน t (0.0 - 1.0)"""      # อธิบายว่า t=0 คือจุด a, t=1 คือจุด b
    return (int(a[0] + (b[0]-a[0]) * t), int(a[1] + (b[1]-a[1]) * t))  # คำนวณพิกัดใหม่ตามสัดส่วน t


def catmull_rom_point(p0, p1, p2, p3, t):
    # แก้ไข: ฟังก์ชันใหม่ — คำนวณจุดบนเส้นโค้ง Catmull-Rom spline ที่พารามิเตอร์ t (0-1)
    # ใช้ 4 จุดควบคุม (p0,p1,p2,p3) เพื่อสร้างจุดบนเส้นโค้งช่วง p1->p2 ที่ "โค้งนุ่ม"
    # ต่างจาก lerp_point ที่ได้แค่เส้นตรง Catmull-Rom จะทำให้แนวกระดูกสันหลังดูโค้งสมจริง
    t2 = t * t                                                  # t ยกกำลังสอง (ใช้ในสูตร cubic)
    t3 = t2 * t                                                 # t ยกกำลังสาม (ใช้ในสูตร cubic)
    x = 0.5 * (                                                 # สูตร Catmull-Rom สำหรับแกน x
        (2 * p1[0]) +                                            # เทอมที่ 1: 2*P1
        (-p0[0] + p2[0]) * t +                                   # เทอมที่ 2: (-P0+P2)*t
        (2*p0[0] - 5*p1[0] + 4*p2[0] - p3[0]) * t2 +              # เทอมที่ 3: สัมประสิทธิ์ความโค้ง * t^2
        (-p0[0] + 3*p1[0] - 3*p2[0] + p3[0]) * t3                # เทอมที่ 4: สัมประสิทธิ์ปลายเส้น * t^3
    )
    y = 0.5 * (                                                 # สูตร Catmull-Rom สำหรับแกน y (สมมาตรกับแกน x)
        (2 * p1[1]) +                                            # เทอมที่ 1: 2*P1
        (-p0[1] + p2[1]) * t +                                   # เทอมที่ 2: (-P0+P2)*t
        (2*p0[1] - 5*p1[1] + 4*p2[1] - p3[1]) * t2 +              # เทอมที่ 3: สัมประสิทธิ์ความโค้ง * t^2
        (-p0[1] + 3*p1[1] - 3*p2[1] + p3[1]) * t3                # เทอมที่ 4: สัมประสิทธิ์ปลายเส้น * t^3
    )
    return (int(x), int(y))                                     # คืนค่าพิกัดจุดบนเส้นโค้งแบบ integer


def build_spine_points(ear_mid, sh_mid, hip_mid, points_per_segment=6):
    # แก้ไข: ฟังก์ชันนี้ปรับปรุงใหม่ทั้งหมด — จากเดิมสร้างแค่ 6 จุดตรง ๆ (lerp)
    # ตอนนี้เปลี่ยนมาใช้ Catmull-Rom spline สุ่มจุดถี่ขึ้นมาก (ปรับ points_per_segment ได้)
    # ทำให้เห็นจุดข้อต่อกระดูกสันหลังละเอียดเหมือนมีหลายปล้อง (vertebrae) จริง ๆ
    """
    สร้างจุดข้อต่อกระดูกสันหลังละเอียด โดยใช้เส้นโค้ง Catmull-Rom
    ผ่าน "จุดควบคุม" หลัก 4 จุด: หู -> คอ -> ไหล่ -> เอว -> สะโพก
    แล้วสุ่มจุดย่อยถี่ ๆ ระหว่างแต่ละคู่จุดควบคุมตาม points_per_segment
    """
    neck    = lerp_point(ear_mid, sh_mid, 0.4)                   # จุดควบคุมที่โคนคอ (40% ระหว่างหู-ไหล่)
    waist   = lerp_point(sh_mid, hip_mid, 0.55)                  # จุดควบคุมที่เอว (55% ระหว่างไหล่-สะโพก)

    control_pts = [ear_mid, neck, sh_mid, waist, hip_mid]         # ลิสต์จุดควบคุมหลักตามแนวสันหลัง (บนลงล่าง)

    # แก้ไข: เพิ่มจุดหลอก (phantom point) หัว-ท้าย เพื่อให้ Catmull-Rom คำนวณช่วงปลายได้
    # (สูตร Catmull-Rom ต้องการจุดก่อนหน้าและจุดถัดไปเสมอ แม้แต่ที่ปลายเส้น)
    ext_pts = [control_pts[0]] + control_pts + [control_pts[-1]]  # เติมจุดซ้ำที่หัวและท้ายลิสต์

    # แก้ไข: เพิ่ม major_indices ใหม่ — เก็บตำแหน่ง index ใน fine_points ที่ตรงกับ "จุดข้อต่อหลัก"
    # (หู, คอ, ไหล่, เอว, สะโพก) ไว้ต่างหาก เพื่อให้วาดจุดพวกนี้ด้วยขนาดเดิม (เท่าเวอร์ชันก่อนหน้า)
    # ส่วนจุดย่อยที่แทรกเพิ่มจาก Catmull-Rom จะถูกวาดเล็กกว่า เพื่อให้เห็นเส้นโค้งละเอียดแต่จุดคอไม่เปลี่ยนขนาด
    fine_points   = []                                            # ลิสต์เก็บจุดข้อต่อละเอียดที่จะคืนค่า
    major_indices = []                                            # ลิสต์เก็บ index ของจุดข้อต่อหลัก (หู/คอ/ไหล่/เอว/สะโพก)
    for i in range(1, len(ext_pts) - 2):                          # วนตามแต่ละช่วง (segment) ระหว่างจุดควบคุม
        p0, p1, p2, p3 = ext_pts[i-1], ext_pts[i], ext_pts[i+1], ext_pts[i+2]  # ดึง 4 จุดควบคุมของช่วงนี้
        steps = points_per_segment if i < len(ext_pts) - 3 else points_per_segment + 1  # ช่วงสุดท้ายเผื่อจุดปลาย
        for s in range(steps):                                    # วนสุ่มจุดย่อยถี่ ๆ ภายในช่วงนี้
            t = s / points_per_segment                            # คำนวณค่า t (0 ถึงเกือบ 1) ตามตำแหน่งย่อย
            if s == 0:                                            # แก้ไข: t=0 คือจุดที่ตรงกับจุดควบคุมหลักพอดี (p1)
                major_indices.append(len(fine_points))             # แก้ไข: บันทึก index นี้ไว้เป็นจุดข้อต่อหลัก
            fine_points.append(catmull_rom_point(p0, p1, p2, p3, t))  # คำนวณจุดบนเส้นโค้งแล้วเพิ่มเข้าลิสต์

    major_indices.append(len(fine_points))                        # แก้ไข: จุดสะโพก (hip_mid) ที่เติมท้ายก็เป็นจุดหลักด้วย
    fine_points.append(hip_mid)                                   # เติมจุดสุดท้าย (สะโพก) ให้ครบเส้นพอดี
    return fine_points, major_indices                             # คืนทั้งจุดข้อต่อละเอียด และ index ของจุดหลัก


def lm_px(lm, w, h):                                              # ฟังก์ชันแปลงพิกัด normalized -> pixel
    """แปลง NormalizedLandmark → pixel"""                          # อธิบายหน้าที่ฟังก์ชัน
    return (int(lm.x * w), int(lm.y * h))                          # คูณค่า x,y (0-1) ด้วยความกว้าง/สูงจริง


def draw_skeleton(frame, lms, w, h, color=(200, 200, 200)):        # ฟังก์ชันวาดโครงกระดูกทั้งตัว
    """วาดโครงกระดูก pose"""                                        # อธิบายหน้าที่ฟังก์ชัน
    pts = [lm_px(lm, w, h) for lm in lms]                            # แปลง landmark ทุกจุดเป็นพิกัด pixel
    for conn in CONNECTIONS:                                        # วนตามเส้นเชื่อมมาตรฐานของ MediaPipe
        s, e = conn.start, conn.end                                  # ดึง index จุดเริ่มและจุดปลายของเส้น
        if s < len(pts) and e < len(pts):                            # กันกรณี index เกินขอบเขตลิสต์
            cv2.line(frame, pts[s], pts[e], color, 2)                 # วาดเส้นเชื่อมระหว่างจุดสองจุด
    for i, (x, y) in enumerate(pts):                                 # วนตามจุด landmark ทุกจุด
        cv2.circle(frame, (x, y), 4, (0, 200, 255), -1)               # วาดจุดวงกลมเล็ก ๆ แทน landmark


def draw_spine_line(frame, spine_points, major_indices, color):
    # แก้ไข: เพิ่มพารามิเตอร์ major_indices — ใช้แยกว่าจุดไหนเป็น "จุดข้อต่อหลัก" (หู/คอ/ไหล่/เอว/สะโพก)
    # เพื่อวาดจุดเหล่านี้ด้วยขนาดเท่าเวอร์ชันก่อนหน้า (ตามที่ขอให้จุดคอกลับไปเป็นเท่าเดิม)
    # ส่วนจุดย่อยที่แทรกจากเส้นโค้ง Catmull-Rom ยังวาดเล็ก ๆ เพื่อให้เห็นความละเอียดของเส้นเหมือนเดิม
    """วาดแนวกระดูกสันหลังแบบละเอียด (จุดข้อต่อหลักขนาดเท่าเดิม + จุดย่อยจากเส้นโค้ง)"""  # อธิบายหน้าที่ฟังก์ชัน
    n = len(spine_points)                                            # นับจำนวนจุดข้อต่อทั้งหมดที่จะวาด
    major_set = set(major_indices)                                   # แก้ไข: แปลงเป็น set เพื่อเช็ค index ได้เร็วขึ้น

    for i in range(n - 1):                                           # วนวาดเส้นเชื่อมระหว่างจุดที่ติดกันทีละคู่
        cv2.line(frame, spine_points[i], spine_points[i+1], color, 2, cv2.LINE_AA)  # วาดเส้นบาง ๆ แบบ anti-alias

    for i, pt in enumerate(spine_points):                            # วนวาดจุดข้อต่อทีละจุด
        if i in major_set:                                           # แก้ไข: ถ้าเป็นจุดข้อต่อหลัก (รวมจุดคอ) ให้วาดขนาดเดิม
            is_endpoint = i == 0 or i == n - 1                        # เช็คว่าเป็นจุดหัว (หู) หรือจุดท้าย (สะโพก) ไหม
            radius = 8 if is_endpoint else 6                          # แก้ไข: คืนขนาดเดิม — หัวท้าย 8, คอ/ไหล่/เอว 6
        else:                                                         # ถ้าเป็นจุดย่อยที่แทรกจากเส้นโค้งเท่านั้น
            radius = 3                                                # วาดเล็ก ๆ ให้เห็นความละเอียดของเส้นโค้ง
        cv2.circle(frame, pt, radius, color, -1)                       # วาดวงกลมทึบสีตามสถานะท่าทาง
        cv2.circle(frame, pt, radius, (255, 255, 255), 1)              # วาดขอบขาวบาง ๆ ให้จุดข้อต่อดูเด่นขึ้น


def draw_rounded_rect(img, x1, y1, x2, y2, r, color, alpha=0.6):     # ฟังก์ชันวาดกล่องพื้นหลังโปร่งใสมุมโค้ง
    """วาดกล่องโปร่งใส"""                                              # อธิบายหน้าที่ฟังก์ชัน
    overlay = img.copy()                                               # ทำสำเนาภาพไว้วาดทับแบบโปร่งใส
    cv2.rectangle(overlay, (x1+r, y1), (x2-r, y2), color, -1)          # วาดสี่เหลี่ยมแนวนอนตรงกลาง (เว้นมุม)
    cv2.rectangle(overlay, (x1, y1+r), (x2, y2-r), color, -1)          # วาดสี่เหลี่ยมแนวตั้งตรงกลาง (เว้นมุม)
    for cx, cy in [(x1+r, y1+r), (x2-r, y1+r), (x1+r, y2-r), (x2-r, y2-r)]:  # วนตามมุมทั้ง 4 ของกล่อง
        cv2.circle(overlay, (cx, cy), r, color, -1)                     # วาดวงกลมเติมมุมให้โค้งมน
    cv2.addWeighted(overlay, alpha, img, 1-alpha, 0, img)               # ผสมภาพ overlay กับภาพจริงให้โปร่งแสง


def notify_line_async(message):                                       # ฟังก์ชันส่งข้อความ LINE แบบ background
    # แก้ไข: ฟังก์ชันใหม่ — ส่งข้อความไป line_chat service ในเธรดแยก
    """ส่งข้อความไป LINE ผ่าน line_chat service ในเธรดแยกเพื่อไม่ให้ภาพจากกล้องกระตุก"""
    if not LINE_MODULE_AVAILABLE or not line_is_configured():          # เช็คว่า requests พร้อมและค่า target ถูกตั้ง
        return                                                          # ถ้ายังไม่พร้อม ออกจากฟังก์ชันทันที ไม่ส่ง
    threading.Thread(target=send_line_alert, args=(message,), daemon=True).start()  # สร้างเธรดใหม่ส่งข้อความแล้วรันทันที


# ==================== ตั้งค่า PoseLandmarker ====================
options = mp_vision.PoseLandmarkerOptions(                             # สร้าง object เก็บค่าตั้งค่าโมเดล pose
    base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),    # ระบุ path ไฟล์โมเดลที่จะโหลด
    running_mode=mp_vision.RunningMode.VIDEO,                           # ตั้งโหมดวิดีโอ (ประมวลผลทีละเฟรมต่อเนื่อง)
    min_pose_detection_confidence=0.5,                                  # ความมั่นใจขั้นต่ำที่จะถือว่า "เจอคน"
    min_pose_presence_confidence=0.5,                                   # ความมั่นใจขั้นต่ำว่า pose ยังอยู่ในเฟรม
    min_tracking_confidence=0.5,                                        # ความมั่นใจขั้นต่ำในการติดตามท่าทางต่อเนื่อง
)
detector = mp_vision.PoseLandmarker.create_from_options(options)        # สร้างตัวตรวจจับ pose จริงจากค่าตั้งค่าด้านบน

# ==================== เปิดกล้อง ====================
cap = cv2.VideoCapture(0)                                               # เปิดกล้องตัวแรกของเครื่อง (index 0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)                                 # ตั้งความกว้างเฟรมภาพเป็น 1280 พิกเซล
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)                                 # ตั้งความสูงเฟรมภาพเป็น 720 พิกเซล

print("กด Q / ESC เพื่อออก  |  กด R เพื่อ reset baseline")               # แจ้งคีย์ลัดให้ผู้ใช้ทราบตอนเริ่มโปรแกรม
if LINE_MODULE_AVAILABLE and line_is_configured():                      # กรณีมีโมดูล LINE และตั้งค่าครบแล้ว
    print("[LINE] เชื่อมต่อระบบแจ้งเตือน LINE พร้อมใช้งาน")               # แจ้งว่า LINE พร้อมใช้งาน
elif LINE_MODULE_AVAILABLE:                                              # กรณีมีไฟล์โมดูลแต่ยังตั้งค่าไม่ครบ
    print("[LINE] พบไฟล์ line_notify.py แต่ยังไม่ได้ตั้งค่า token/user id (ดูคอมเมนต์ในไฟล์นั้น)")  # แจ้งเตือนให้ตั้งค่า
else:                                                                     # กรณีไม่พบไฟล์โมดูลเลย
    print("[LINE] ไม่พบไฟล์ line_notify.py — ระบบแจ้งเตือน LINE ถูกปิดใช้งาน")  # แจ้งว่าปิดใช้งานฟีเจอร์ LINE

timestamp_ms  = 0                                                        # ตัวนับเวลา (ms) ป้อนให้ MediaPipe VIDEO mode
bad_start     = None                                                     # เวลาที่เริ่มนั่งท่าไม่ดี (None = ยังไม่เริ่ม)
last_alert_t  = 0                                                        # เวลาที่เตือนบนจอครั้งล่าสุด (ใช้คุม cooldown)
alert_msg     = ""                                                       # ข้อความเตือนปัจจุบันที่จะโชว์บนจอ
alert_until   = 0                                                        # เวลาที่จะซ่อนกล่องเตือนบนจอ (timestamp)
good_frames   = 0                                                        # นับจำนวนเฟรมติดต่อกันที่ท่าทางดี
bad_frames    = 0                                                        # นับจำนวนเฟรมติดต่อกันที่ท่าทางไม่ดี

# แก้ไข: ตัวแปรใหม่สำหรับคุมการส่งแจ้งเตือนไป LINE แยกจากการเตือนบนจอ (คนละ cooldown กัน)
last_line_alert_t = 0                                                    # เวลาที่ส่งข้อความ LINE ครั้งล่าสุด

# สถิติ session
session_start = time.time()                                              # เวลาที่เริ่ม session (ใช้คำนวณเวลารวม)
total_bad_sec = 0.0                                                       # เวลารวมทั้งหมดที่นั่งท่าไม่ดี (วินาที)

while cap.isOpened():                                                     # ลูปหลัก: ทำงานตราบเท่าที่กล้องยังเปิดอยู่
    ok, frame = cap.read()                                                 # อ่านเฟรมภาพปัจจุบันจากกล้อง
    if not ok:                                                             # ถ้าอ่านภาพไม่สำเร็จ (กล้องหลุด/ปิด)
        break                                                               # ออกจากลูปหลักทันที

    frame = cv2.flip(frame, 1)                                             # กลับภาพซ้าย-ขวา ให้เหมือนกระจกเงา
    H, W = frame.shape[:2]                                                 # ดึงความสูง (H) และความกว้าง (W) ของเฟรม
    now  = time.time()                                                     # บันทึกเวลาปัจจุบัน (timestamp) ของเฟรมนี้

    rgb      = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)                      # แปลงสีจาก BGR (OpenCV) เป็น RGB (MediaPipe)
    mp_img   = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)         # ห่อภาพ RGB เป็น mp.Image สำหรับโมเดล
    timestamp_ms += 33                                                     # เพิ่มตัวนับเวลา ~33ms ต่อเฟรม (ประมาณ 30fps)
    result   = detector.detect_for_video(mp_img, timestamp_ms)              # ส่งภาพเข้าโมเดลเพื่อตรวจจับท่าทาง

    posture_ok   = True                                                    # ตั้งค่าเริ่มต้นว่าท่าทางโอเคไว้ก่อน
    issues       = []                                                      # ลิสต์เก็บข้อความสั้นสำหรับกล่อง metrics
    tips         = []                                                      # แก้ไข: ลิสต์เก็บคำแนะนำเต็ม ๆ สำหรับกล่องเตือน
    spine_angle  = None                                                    # ตัวแปรมุมกระดูกสันหลัง (ยังไม่คำนวณ)
    head_forward = None                                                    # ตัวแปรระยะคอยื่น (ยังไม่คำนวณ)

    if result.pose_landmarks:                                              # ถ้าโมเดลตรวจพบคนในเฟรมนี้
        lms = result.pose_landmarks[0]                                      # ดึง landmark ของคนคนแรกที่เจอ

        # ---- ดึงจุดสำคัญ ----
        l_ear = lm_px(lms[LEFT_EAR],  W, H)                                 # พิกัดพิกเซลของหูซ้าย
        r_ear = lm_px(lms[RIGHT_EAR], W, H)                                 # พิกัดพิกเซลของหูขวา
        l_sh  = lm_px(lms[LEFT_SHOULDER],  W, H)                            # พิกัดพิกเซลของไหล่ซ้าย
        r_sh  = lm_px(lms[RIGHT_SHOULDER], W, H)                            # พิกัดพิกเซลของไหล่ขวา
        l_hip = lm_px(lms[LEFT_HIP],  W, H)                                 # พิกัดพิกเซลของสะโพกซ้าย
        r_hip = lm_px(lms[RIGHT_HIP], W, H)                                 # พิกัดพิกเซลของสะโพกขวา

        ear_mid = midpoint(l_ear, r_ear)                                    # จุดกึ่งกลางระหว่างหูซ้าย-ขวา
        sh_mid  = midpoint(l_sh,  r_sh)                                     # จุดกึ่งกลางระหว่างไหล่ซ้าย-ขวา
        hip_mid = midpoint(l_hip, r_hip)                                    # จุดกึ่งกลางระหว่างสะโพกซ้าย-ขวา

        # ---- วาดโครงกระดูก ----
        draw_skeleton(frame, lms, W, H)                                     # วาดโครงกระดูกทั้งตัวแบบจาง ๆ เป็นพื้นหลัง

        # ---- 1. มุมกระดูกสันหลัง (หู → ไหล่ → สะโพก) ----
        spine_angle = angle_3pts(ear_mid, sh_mid, hip_mid)                  # คำนวณมุมโค้งของหลังจาก 3 จุดหลัก

        # ---- 2. Forward Head (หูยื่นไปข้างหน้ากว่าไหล่) ----
        # ใช้ normalized coords เพื่อให้ distance-independent
        ear_x_n  = (lms[LEFT_EAR].x + lms[RIGHT_EAR].x) / 2                 # ค่าเฉลี่ยตำแหน่ง x ของหู (normalized)
        sh_x_n   = (lms[LEFT_SHOULDER].x + lms[RIGHT_SHOULDER].x) / 2       # ค่าเฉลี่ยตำแหน่ง x ของไหล่ (normalized)
        head_forward = abs(ear_x_n - sh_x_n)                                # ระยะห่างแนวนอนระหว่างหูกับไหล่

        # ---- วิเคราะห์ ----
        # แก้ไข: ข้อความแนะนำวิธีแก้ไข (tips) แยกจากข้อความสั้นสำหรับ metrics (issues)
        if spine_angle < SPINE_ANGLE_WARN:                                  # If the spine angle is below the severe slump threshold
            posture_ok = False                                               # Mark posture as not okay
            issues.append(f"Severe slouch ({spine_angle:.0f}°)")             # Add short issue text to metrics
            tips.append("You are slouching too much. Try sitting up straight, lower your shoulders, and gently lift your chest.")  # Add full tip text
        elif spine_angle < SPINE_ANGLE_GOOD:                                 # If the angle is in the beginning slouch range
            posture_ok = False                                               # Mark posture as not okay
            issues.append(f"Starting to slouch ({spine_angle:.0f}°)")         # Add short issue text to metrics
            tips.append("You are beginning to slouch. Move your hips closer to the chair and straighten your back a bit more.")  # Add full tip text

        if head_forward > HEAD_FORWARD_THRESH:                              # If the head is forward beyond the threshold
            posture_ok = False                                               # Mark posture as not okay
            issues.append("Forward head posture")                          # Add short issue text to metrics
            tips.append("Your head is too far forward. Tuck your chin slightly and adjust your screen to eye level.")  # Add full tip text

        # ---- วาดเส้นกระดูกสันหลัง (ละเอียดขึ้นมากด้วยเส้นโค้ง Catmull-Rom) ----
        # แก้ไข: เรียก build_spine_points() แบบใหม่ที่คืนจุดข้อต่อละเอียดกว่าเดิมหลายเท่า
        color_spine = (0, 220, 80) if posture_ok else (0, 80, 255)          # สีเขียวถ้าท่าดี, สีแดงถ้าท่าไม่ดี
        # แก้ไข: build_spine_points ตอนนี้คืนค่า 2 ตัว (จุดทั้งหมด, index ของจุดข้อต่อหลัก) ต้องรับให้ครบ
        spine_points, major_indices = build_spine_points(ear_mid, sh_mid, hip_mid, points_per_segment=6)  # สร้างจุดข้อต่อละเอียด
        draw_spine_line(frame, spine_points, major_indices, color_spine)    # วาดแนวกระดูกสันหลัง (จุดคอ/ไหล่/เอวขนาดเท่าเดิม)

        # ---- จับเวลาท่าไม่ดี ----
        if not posture_ok:                                                  # ถ้าท่าทางตอนนี้ไม่โอเค
            bad_frames += 1                                                  # เพิ่มตัวนับเฟรมท่าไม่ดีติดต่อกัน
            good_frames = 0                                                  # รีเซ็ตตัวนับเฟรมท่าดีเป็นศูนย์
            if bad_start is None:                                            # ถ้ายังไม่มีจุดเริ่มนั่งไม่ดี
                bad_start = now                                               # บันทึกเวลาเริ่มนั่งไม่ดีตอนนี้
            bad_elapsed = now - bad_start                                    # คำนวณระยะเวลาที่นั่งไม่ดีต่อเนื่องมา
            total_bad_sec += 0.033                                           # สะสมเวลารวมของท่าไม่ดี (~1 เฟรม)

            # --- ใช้ค่าจาก ZONE 2 (เวลาแจ้งเตือนบนจอ) ---
            if bad_elapsed >= BAD_DURATION_TRIGGER and (now - last_alert_t) > ALERT_COOLDOWN_SEC:  # เช็คเงื่อนไข ZONE 2
                # แก้ไข: ใช้ tips (ข้อความแนะนำ) แทน issues (แค่ตัวเลข) ในกล่องเตือนใหญ่
                # แก้ไข: เปลี่ยนสัญลักษณ์ "⚠" เป็นคำว่า "Tex" เพราะฟอนต์ของ OpenCV (Hershey)
                # ไม่รองรับอักขระ emoji/unicode พวกนี้ เวลาแสดงผลจริงจะกลายเป็น "?" แทน
                alert_msg   = "Tex  " + "   ".join(tips)                      # รวมคำแนะนำทั้งหมดเป็นข้อความเดียว
                alert_until = now + ALERT_DISPLAY_SEC                         # ตั้งเวลาที่จะซ่อนกล่องเตือน (ZONE 2)
                last_alert_t = now                                            # บันทึกเวลาที่เตือนล่าสุด (ใช้คุม cooldown)

            # --- ใช้ค่าจาก ZONE 3 (เวลาแจ้งเตือนเข้า LINE) ---
            if (bad_elapsed >= LINE_ALERT_DURATION_TRIGGER                    # เช็คว่าค่อมนานพอตามเกณฑ์ ZONE 3 หรือยัง
                    and (now - last_line_alert_t) > LINE_ALERT_COOLDOWN_SEC):  # และพ้น cooldown ของ ZONE 3 หรือยัง
                minutes = int(bad_elapsed // 60)                              # แปลงวินาทีที่ค่อมเป็นจำนวนนาที (ปัดลง)
                line_msg = (                                                  # ประกอบข้อความที่จะส่งเข้า LINE
                    "🪑 Posture Guard แจ้งเตือน\n"                            # หัวข้อข้อความ
                    f"You have been sitting with a hunched back or a forward-leaning neck for {minutes} minutes.\n"  # บอกระยะเวลาที่ค่อม
                    + "\n".join(f"- {t}" for t in tips)                        # แสดงคำแนะนำแต่ละข้อเป็นบูลเลต
                    + "\nTry standing up, stretching, or adjusting your posture."       # ปิดท้ายด้วยคำแนะนำรวม
                )
                notify_line_async(line_msg)                                   # ส่งข้อความไป LINE แบบ background
                last_line_alert_t = now                                       # บันทึกเวลาที่ส่ง LINE ล่าสุด (ZONE 3)
        else:                                                                 # ถ้าท่าทางตอนนี้โอเคแล้ว
            good_frames += 1                                                  # เพิ่มตัวนับเฟรมท่าดีติดต่อกัน
            if good_frames > 10:                                              # ถ้าท่าดีต่อเนื่องเกิน 10 เฟรม
                bad_start = None                                              # รีเซ็ตจุดเริ่มนั่งไม่ดี (ถือว่าหายค่อมแล้ว)
            bad_frames = 0                                                    # รีเซ็ตตัวนับเฟรมท่าไม่ดีเป็นศูนย์
    else:                                                                     # ถ้าไม่พบคนในเฟรมนี้เลย
        bad_start = None                                                      # รีเซ็ตจุดเริ่มนั่งไม่ดี (ไม่มีข้อมูลให้เช็ค)

    # ==================== UI ====================
    # --- แถบบน: สถานะ ---
    if result.pose_landmarks:                                                # ถ้าตรวจพบคนในเฟรมนี้
        if posture_ok:                                                        # ถ้าท่าทางโอเคทั้งหมด
            status_color = (30, 180, 30)                                      # สีเขียวสำหรับข้อความสถานะ
            status_text  = "your motion is exactly right!"             # ข้อความให้กำลังใจ
        elif spine_angle is not None and spine_angle < SPINE_ANGLE_WARN:       # ถ้าค่อมชัดเจนตามเกณฑ์ ZONE 1
            status_color = (0, 60, 220)                                       # สีแดงสำหรับข้อความสถานะ
            status_text  = "your posture is not correct!"        # ข้อความเตือนหนัก
        else:                                                                  # กรณีเริ่มค่อมหรือคอยื่นเล็กน้อย
            status_color = (0, 140, 255)                                       # สีส้มสำหรับข้อความสถานะ
            status_text  = "your posture needs improvement"             # ข้อความเตือนเบา ๆ
    else:                                                                      # ถ้าไม่พบคนในเฟรม
        status_color = (80, 80, 80)                                            # สีเทาสำหรับข้อความสถานะ
        status_text  = "—  มองไม่เห็นท่าทาง ลองขยับกล้อง/แสงดูนะ"               # ข้อความแจ้งปัญหาการมองเห็น

    draw_rounded_rect(frame, 0, 0, W, 68, 0, (20, 20, 20), alpha=0.65)         # วาดแถบพื้นหลังโปร่งใสด้านบนจอ
    cv2.putText(frame, status_text, (20, 46),                                  # เขียนข้อความสถานะลงบนแถบบน
                cv2.FONT_HERSHEY_DUPLEX, 1.1, status_color, 2, cv2.LINE_AA)     # กำหนดฟอนต์ ขนาด สี ความหนา

    # --- แถบขวา: metrics ---
    if result.pose_landmarks and spine_angle is not None:                      # ถ้ามีข้อมูลมุมหลังให้แสดง
        draw_rounded_rect(frame, W-280, 80, W, 220, 8, (20, 20, 20), alpha=0.6)  # วาดกล่องพื้นหลังด้านขวาบน
        metrics = [                                                            # ลิสต์ข้อมูลตัวเลขที่จะแสดง
            ("Spine Angle", f"{spine_angle:.1f} deg"),                          # แถวมุมกระดูกสันหลัง
            ("Head Fwd",    f"{head_forward:.3f}"),                             # แถวระยะคอยื่น
            ("Bad time",    f"{total_bad_sec:.0f} s"),                          # แถวเวลาสะสมที่ท่าไม่ดี
        ]
        for i, (k, v) in enumerate(metrics):                                    # วนแสดงแต่ละแถวของ metrics
            cy = 112 + i * 42                                                    # คำนวณตำแหน่งแนวตั้งของแถวนี้
            cv2.putText(frame, k, (W-268, cy),                                   # เขียนชื่อ metric (label)
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (160,160,160), 1)          # ฟอนต์เล็ก สีเทาอ่อน
            cv2.putText(frame, v, (W-268, cy+20),                                # เขียนค่าตัวเลขของ metric
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,220,255), 2)            # ฟอนต์ใหญ่กว่า สีฟ้า

    # --- กล่องเตือน ---
    # แก้ไข: ขยายกล่องเตือนเป็น 2 บรรทัด เผื่อข้อความแนะนำยาวขึ้น
    if now < alert_until and alert_msg:                                        # ถ้ายังอยู่ในช่วงเวลาที่ต้องโชว์ (ZONE 2)
        draw_rounded_rect(frame, 0, H-110, W, H, 0, (0, 30, 140), alpha=0.75)    # วาดกล่องพื้นหลังสีน้ำเงินด้านล่างจอ
        max_chars_per_line = max(1, W // 13)                                    # คำนวณจำนวนตัวอักษรสูงสุดต่อบรรทัดคร่าว ๆ
        line1 = alert_msg[:max_chars_per_line]                                  # ตัดข้อความส่วนแรกไปแสดงบรรทัดที่ 1
        line2 = alert_msg[max_chars_per_line:max_chars_per_line*2]              # ตัดข้อความส่วนที่สองไปแสดงบรรทัดที่ 2
        cv2.putText(frame, line1, (20, H-68),                                   # เขียนข้อความบรรทัดที่ 1
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 220, 255), 2, cv2.LINE_AA)  # กำหนดฟอนต์ ขนาด สี
        if line2:                                                               # ถ้ามีข้อความเหลือสำหรับบรรทัดที่ 2
            cv2.putText(frame, line2, (20, H-32),                                # เขียนข้อความบรรทัดที่ 2
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 220, 255), 2, cv2.LINE_AA)  # กำหนดฟอนต์ ขนาด สี

    # --- เวลา session ---
    elapsed = int(now - session_start)                                         # คำนวณเวลารวมตั้งแต่เริ่ม session (วินาที)
    cv2.putText(frame, f"Session {elapsed//60:02d}:{elapsed%60:02d}",           # เขียนเวลารวมในรูปแบบ นาที:วินาที
                (20, H-15), cv2.FONT_HERSHEY_SIMPLEX,                           # ตำแหน่งมุมล่างซ้ายของจอ
                0.6, (140,140,140), 1, cv2.LINE_AA)                             # ขนาดฟอนต์เล็ก สีเทา

    # --- คีย์ลัด ---
    cv2.putText(frame, "Q=Quit  R=Reset", (W-230, H-15),                       # เขียนข้อความคีย์ลัดมุมล่างขวา
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (120,120,120), 1)               # ขนาดฟอนต์เล็ก สีเทาอ่อน

    cv2.imshow("Posture Guard — Office Syndrome Prevention", frame)            # แสดงภาพเฟรมนี้ในหน้าต่างโปรแกรม
    key = cv2.waitKey(1) & 0xFF                                                # อ่านค่าปุ่มที่ผู้ใช้กด (รอ 1ms)
    if key in (ord("q"), ord("Q"), 27):                                        # ถ้ากด Q, q หรือ ESC (27)
        break                                                                   # ออกจากลูปหลัก จบโปรแกรม
    elif key in (ord("r"), ord("R")):                                          # ถ้ากด R หรือ r
        bad_start     = None                                                    # รีเซ็ตจุดเริ่มนั่งไม่ดี
        total_bad_sec = 0.0                                                     # รีเซ็ตเวลาสะสมท่าไม่ดีเป็นศูนย์
        session_start = time.time()                                             # รีเซ็ตเวลาเริ่ม session ใหม่
        last_line_alert_t = 0                                                   # แก้ไข: รีเซ็ต cooldown ของ LINE ด้วย (ZONE 3)
        print("Reset สถิติแล้ว")                                                # แจ้งผู้ใช้ว่า reset สำเร็จ

cap.release()                                                                    # คืนอุปกรณ์กล้องกลับให้ระบบ
cv2.destroyAllWindows()                                                          # ปิดหน้าต่างแสดงผลทั้งหมดของ OpenCV
detector.close()                                                                 # ปิดตัวตรวจจับ pose ของ MediaPipe
print(f"จบ session  |  นั่งไม่ดีรวม {total_bad_sec:.0f} วินาที")                  # สรุปผลรวมเวลาที่นั่งไม่ดีตอนจบโปรแกรม