import tkinter as tk
import ctypes

class SimpleOverlayTest:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()  # 隐藏主窗口
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes("-fullscreen", True)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-transparentcolor", "black")
        self.overlay.overrideredirect(True)
        
        self.canvas = tk.Canvas(self.overlay, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # 尝试设置窗口保护（可选）
        try:
            hwnd = int(self.overlay.frame(), 16)
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 17)
        except:
            pass
        
        # 强制窗口显示并提升
        self.overlay.lift()
        self.overlay.update()
        
        # 画中心十字（屏幕正中央）
        screen_w = self.overlay.winfo_screenwidth()
        screen_h = self.overlay.winfo_screenheight()
        cx, cy = screen_w // 2, screen_h // 2
        self.canvas.create_line(cx-20, cy, cx+20, cy, fill="white", width=3)
        self.canvas.create_line(cx, cy-20, cx, cy+20, fill="white", width=3)
        
        # 画一个红色圆点
        self.canvas.create_oval(cx-10, cy-10, cx+10, cy+10, fill="red", outline="white")
        
        # 画一个蓝色矩形和文字
        self.canvas.create_rectangle(cx-30, cy-50, cx+30, cy-10, outline="blue", width=3)
        self.canvas.create_text(cx, cy-30, text="Test 100m", fill="yellow", font=("Arial", 14))
        
        print("Overlay 窗口已创建，应该可以看到十字线、红点、矩形和文字。按 ESC 退出。")
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.mainloop()

if __name__ == "__main__":
    app = SimpleOverlayTest()