import tkinter as tk
import threading, time, mss, cv2
from region_manager import RegionManager
from gesture_identifier import GestureIdentifier

class GestureTester:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("姿势识别测试台")
        self.root.geometry("300x350")
        self.rm = RegionManager(self.root)
        self.gesture_id = GestureIdentifier(self.rm, threshold=0.55)
        self.is_detecting = False
        
        self.lbl = tk.Label(self.root, text="准备就绪", font=("Arial", 20))
        self.lbl.pack(pady=50)
        self.btn = tk.Button(self.root, text="开始监测", command=self.toggle)
        self.btn.pack()
        self.root.mainloop()

    def toggle(self):
        self.is_detecting = not self.is_detecting
        if self.is_detecting:
            threading.Thread(target=self.loop, daemon=True).start()

    def loop(self):
        with mss.mss() as sct:
            while self.is_detecting:
                name, score, img = self.gesture_id.identify_current_gesture(sct)
                if img is not None: cv2.imshow("Debug", img)
                cv2.waitKey(1)
                self.root.after(0, lambda: self.lbl.config(text=f"{name or '未知'} ({score:.2f})"))
                time.sleep(0.1)

if __name__ == "__main__":
    GestureTester()