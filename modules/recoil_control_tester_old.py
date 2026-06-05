import tkinter as tk
from modules.recoil_control_old import RecoilControlModule

class RecoilTester:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("压枪逻辑中枢 - 测试台")
        self.root.geometry("400x480")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")
        
        # 实例化我们的压枪模块
        self.rc = RecoilControlModule()
        self.init_ui()

    def init_ui(self):
        tk.Label(self.root, text="🕹️ 压枪与连发测试台", fg="white", bg="#2C3E50", font=("Microsoft YaHei", 14, "bold")).pack(pady=10)
        
        # 1. 总开关控制
        self.btn_toggle = tk.Button(self.root, text="▶️ 开启全局压枪 (OFF)", command=self.toggle_engine, bg="#E74C3C", fg="white", font=("Microsoft YaHei", 10, "bold"))
        self.btn_toggle.pack(fill="x", padx=40, pady=10)
        
        # 2. 模拟识别到的武器
        tk.Label(self.root, text="1. 模拟当前手持武器 (视觉识别传入)", fg="#BDC3C7", bg="#2C3E50").pack(pady=(10, 0))
        f_wp = tk.Frame(self.root, bg="#2C3E50")
        f_wp.pack(pady=5)
        tk.Button(f_wp, text="空手(None)", command=lambda: self.rc.update_weapon(None), width=8).pack(side="left", padx=5)
        tk.Button(f_wp, text="M416", command=lambda: self.rc.update_weapon("M416"), width=8).pack(side="left", padx=5)
        tk.Button(f_wp, text="M16A4(连点)", command=lambda: self.rc.update_weapon("M16A4"), width=10).pack(side="left", padx=5)
        
        # 3. 模拟识别到的姿势
        tk.Label(self.root, text="2. 模拟人物姿势 (姿态检测传入)", fg="#BDC3C7", bg="#2C3E50").pack(pady=(10, 0))
        f_st = tk.Frame(self.root, bg="#2C3E50")
        f_st.pack(pady=5)
        tk.Button(f_st, text="站立(x1.0)", command=lambda: self.rc.update_stance("stand"), width=8).pack(side="left", padx=5)
        tk.Button(f_st, text="蹲下(x0.8)", command=lambda: self.rc.update_stance("squat"), width=8).pack(side="left", padx=5)
        tk.Button(f_st, text="趴下(x0.6)", command=lambda: self.rc.update_stance("lie"), width=8).pack(side="left", padx=5)
        
        # 4. 模拟当前的倍镜
        tk.Label(self.root, text="3. 模拟当前倍镜 (右键开镜状态)", fg="#BDC3C7", bg="#2C3E50").pack(pady=(10, 0))
        f_sc = tk.Frame(self.root, bg="#2C3E50")
        f_sc.pack(pady=5)
        tk.Button(f_sc, text="腰射(x1.0)", command=lambda: self.rc.update_scope("hip"), width=8).pack(side="left", padx=5)
        tk.Button(f_sc, text="红点(x1.2)", command=lambda: self.rc.update_scope("red_dot"), width=8).pack(side="left", padx=5)
        tk.Button(f_sc, text="三倍(x3.0)", command=lambda: self.rc.update_scope("x3"), width=8).pack(side="left", padx=5)
        
        tk.Label(self.root, text="💡 提示: 开启压枪后，随便选个枪，按住左键测试。\n留意控制台打印的计算公式。", fg="#F1C40F", bg="#2C3E50", font=("Microsoft YaHei", 9)).pack(pady=15)

    def toggle_engine(self):
        new_state = not self.rc.is_enabled
        self.rc.set_enabled(new_state)
        
        if new_state:
            self.btn_toggle.config(text="⏹️ 停止全局压枪 (ON)", bg="#2ECC71")
        else:
            self.btn_toggle.config(text="▶️ 开启全局压枪 (OFF)", bg="#E74C3C")

    def on_closing(self):
        self.rc.shutdown()
        self.root.destroy()

if __name__ == "__main__":
    app = RecoilTester()
    app.root.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.root.mainloop()