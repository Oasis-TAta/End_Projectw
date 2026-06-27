# main camera
import cv2
import datetime

cap1 = cv2.VideoCapture(0)
cap2 = cv2.VideoCapture(1)
cap3 = cv2.VideoCapture(2)

while True:
    ret1, frame1 = cap1.read()
    ret2, frame2 = cap2.read()
    ret3, frame3 = cap3.read()

    # ตรวจสอบว่าสามารถอ่านเฟรมภาพได้หรือไม่
    if ret1:
        # พิมพ์เวลาลงบนภาพ
        cv2.putText(frame1, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        
        # แสดงผลภาพ
        cv2.imshow('Camera 1', frame1)
    else:
        print("ไม่สามารถรับภาพจาก Camera 1 ได้")
        break # ออกจากลูปหากไม่พบสัญญาณภาพ

    cv2.imshow('Camera 2', frame2)
    cv2.imshow('Camera 3', frame3)

    # กดปุ่ม 'q' เพื่อออกจากโปรแกรม (รอรับคำสั่ง 1 มิลลิวินาที)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap1.release()
cap2.release()
cap3.release()
cv2.destroyAllWindows()