import tkinter as tk
import threading
import time
import mss
import cv2
import numpy as np
from region_manager import RegionManager
from weapon_identifier import WeaponIdentifier

class WeaponTester:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("武器识别中枢 - 测试台")
        self.root.geometry("350x400")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")
        
        # 设置识别帧率
        self.fps = 30
        
        self.rm = RegionManager(self.root)
        # 实例化时阈值设为 0.50
        self.weapon_id = WeaponIdentifier(self.rm, threshold=0.50)
        
        self.is_detecting = False
        self.detect_thread = None
        self.init_ui()

    def init_ui(self):
        tk.Label(self.root, text="🔫 武器视觉识别测试", fg="white", bg="#2C3E50", font=("Microsoft YaHei", 14, "bold")).pack(pady=15)
        
        self.frame_controls = tk.Frame(self.root, bg="#2C3E50")
        self.frame_controls.pack(fill="x", padx=20, pady=10)
        
        self.btn_detect = tk.Button(self.frame_controls, text=f"▶️ 开始实时识别 (包含视觉监控 - {self.fps}FPS)", command=self.toggle_detection, bg="#E74C3C", fg="white", font=("Microsoft YaHei", 10, "bold"))
        self.btn_detect.pack(fill="x", pady=5)
        
        tk.Frame(self.root, height=2, bg="#34495E").pack(fill="x", pady=15)
        
        tk.Label(self.root, text="当前识别结果", fg="#BDC3C7", bg="#2C3E50", font=("Microsoft YaHei", 10)).pack()
        self.lbl_weapon = tk.Label(self.root, text="未检测到武器", fg="#7F8C8D", bg="#2C3E50", font=("Consolas", 20, "bold"))
        self.lbl_weapon.pack(pady=10)
        
        self.lbl_score = tk.Label(self.root, text="匹配度: 0.00%", fg="#95A5A6", bg="#2C3E50", font=("Consolas", 12))
        self.lbl_score.pack(pady=5)

    def toggle_detection(self):
        self.is_detecting = not self.is_detecting
        if self.is_detecting:
            self.btn_detect.config(text=f"⏹️ 停止实时识别 (关闭监控 - {self.fps}FPS)", bg="#2ECC71")
            self.lbl_weapon.config(text="扫描中...", fg="#F1C40F")
            self.detect_thread = threading.Thread(target=self._detection_loop, daemon=True)
            self.detect_thread.start()
        else:
            self.btn_detect.config(text=f"▶️ 开始实时识别 (包含视觉监控 - {self.fps}FPS)", bg="#E74C3C")
            self.lbl_weapon.config(text="已暂停", fg="#7F8C8D")
            cv2.destroyAllWindows()

    def _detection_loop(self):
        with mss.MSS() as sct:
            while self.is_detecting:
                start_time = time.time()
                
                weapon_name, score, current_img = self.weapon_id.identify_current_weapon(sct)
                self.root.after(0, self._update_ui, weapon_name, score)
                
                if current_img is not None:
                    cv2.imshow("Debug: Live Screenshot", current_img)
                    if weapon_name and weapon_name in self.weapon_id.templates:
                        tpl_img = self.weapon_id.templates[weapon_name][0]
                        cv2.imshow("Debug: Matched Template", tpl_img)
                    
                cv2.waitKey(1)
                
                # 精准帧率控制机制
                elapsed = time.time() - start_time
                sleep_time = max(0, (1.0 / self.fps) - elapsed)
                time.sleep(sleep_time)

    def _update_ui(self, weapon_name, score):
        if not self.is_detecting: return
        if weapon_name:
            self.lbl_weapon.config(text=weapon_name, fg="#2ECC71")
            self.lbl_score.config(text=f"匹配度: {score*100:.1f}%", fg="#2ECC71")
        else:
            self.lbl_weapon.config(text="未识别/空手", fg="#E67E22")
            self.lbl_score.config(text=f"最高噪点匹配: {score*100:.1f}%", fg="#E74C3C")

    def on_closing(self):
        self.is_detecting = False
        cv2.destroyAllWindows()
        self.root.destroy()

if __name__ == "__main__":
    app = WeaponTester()
    app.root.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.root.mainloop()