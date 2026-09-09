# --- ตัวอย่างการเช็คเงื่อนไขมุม/องศาใน Loop กล้อง ---
    # สมมติว่าคำนวณค่าองศาหลังค่อมได้ในตัวแปร back_angle
    ANGLE_THRESHOLD = 150  # ถ้าน้อยกว่า 150 ถือว่าหลังค่อม

    if back_angle < ANGLE_THRESHOLD:
        is_bad_posture = True
        status_text = "Bad Posture"
    else:
        is_bad_posture = False
        status_text = "Good Posture"

    # เรียกส่งแจ้งเตือนเข้า LINE ทันทีเมื่อจับได้ว่านั่งผิดท่า
    check_and_send_alert(is_bad_posture, message="คุณกำลังนั่งหลังค่อม กรุณาปรับท่านั่งครับ")