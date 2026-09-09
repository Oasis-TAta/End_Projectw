import camera

if __name__ == "__main__":
    print("[System] กำลังเริ่มต้นระบบ Posture Guard และเปิดกล้อง...")
    
    # เช็คว่าในไฟล์ camera.py มีฟังก์ชัน main() หรือรันโดยอัตโนมัติ
    if hasattr(camera, 'main'):
        camera.main()
    elif hasattr(camera, 'run'):
        camera.run()