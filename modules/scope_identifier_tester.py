import tkinter as tk
import threading
import time
import mss
import cv2
import os
from region_manager import RegionManager
from scope_identifier import ScopeIdentifier

class ScopeTester:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("倍镜识别中枢 - 测试台")
        self.root.geometry("350x380")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")
        
        self.rm = RegionManager(self.root)
        self.scope_id = ScopeIdentifier(self.rm, threshold=0.55)
        
        self.detect_thread = None
        self.init_ui()

    def init_ui(self):
        tk.Label(self.root, text="🔭 倍镜视觉识别测试", fg="white", bg="#2C3E50", font=("Microsoft YaHei", 14, "bold")).pack(pady=15)
        
        self.btn_detect = tk.Button(self.root, text="▶️ 允许开启倍镜识别 (OFF)", command=self.toggle_detection, bg="#E74C3C", fg="white", font=("Microsoft YaHei", 10, "bold"))
        self.btn_detect.pack(fill="x", padx=40, pady=10)
        
        tk.Frame(self.root, height=2, bg="#34495E").pack(fill="x", pady=15)
        
        tk.Label(self.root, text="当前识别倍镜", fg="#BDC3C7", bg="#2C3E50").pack()
        self.lbl_scope = tk.Label(self.root, text="腰射 (未开启)", fg="#7F8C8D", bg="#2C3E50", font=("Consolas", 20, "bold"))
        self.lbl_scope.pack(pady=10)
        
        self.lbl_score = tk.Label(self.root, text="匹配度: 0.00%", fg="#95A5A6", bg="#2C3E50", font=("Consolas", 12))
        self.lbl_score.pack(pady=5)

    def toggle_detection(self):
        new_state = not self.scope_id.is_enabled
        self.scope_id.set_enabled(new_state)
        
        if new_state:
            self.btn_detect.config(text="⏹️ 停止倍镜识别 (ON)", bg="#2ECC71")
            self.lbl_scope.config(text="扫描中...", fg="#F1C40F")
            self.detect_thread = threading.Thread(target=self._detection_loop, daemon=True)
            self.detect_thread.start()
        else:
            self.btn_detect.config(text="▶️ 允许开启倍镜识别 (OFF)", bg="#E74C3C")
            self.lbl_scope.config(text="腰射 (未开启)", fg="#7F8C8D")
            cv2.destroyAllWindows()

    def _detection_loop(self):
        with mss.MSS() as sct:
            while self.scope_id.is_enabled:
                start_time = time.time()
                
                scope_name, score, current_img = self.scope_id.identify_current_scope(sct)
                self.root.after(0, self._update_ui, scope_name, score)
                
                if current_img is not None:
                    try:
                        # 1. 显示处理后的【游戏实时图】
                        cv2.imshow("Debug: Live Game Screen", current_img)
                        
                        # 2. 显示匹配前使用的【内部模板图】
                        if scope_name and scope_name in self.scope_id.templates:
                            tpl_img = self.scope_id.templates[scope_name][0]["tpl"]
                            cv2.imshow("Debug: Internal Template", tpl_img)
                        else:
                            # 没匹配到时，随便挑一个库里的模板展示，让你对比找原因
                            if self.scope_id.templates:
                                first_key = list(self.scope_id.templates.keys())[0]
                                if self.scope_id.templates[first_key]:
                                    sample_tpl = self.scope_id.templates[first_key][0]["tpl"]
                                    cv2.imshow("Debug: Internal Template", sample_tpl)
                        
                        cv2.waitKey(1)
                    except cv2.error:
                        pass
                
                time.sleep(max(0, 0.05 - (time.time() - start_time)))

    def _update_ui(self, scope_name, score):
        if not self.scope_id.is_enabled: return
        if scope_name:
            self.lbl_scope.config(text=scope_name, fg="#2ECC71")
            self.lbl_score.config(text=f"匹配度: {score*100:.1f}%", fg="#2ECC71")
        else:
            self.lbl_scope.config(text="未识别倍镜", fg="#E67E22")
            self.lbl_score.config(text=f"匹配度: {score*100:.1f}%", fg="#E74C3C")

    def on_closing(self):
        """【防卡死解决方案】：直接瞬间终结主线程和所有的子线程"""
        os._exit(0)

if __name__ == "__main__":
    app = ScopeTester()
    app.root.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.root.mainloop()