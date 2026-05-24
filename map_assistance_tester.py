import tkinter as tk
from tkinter import ttk
from map_assistance import MapPointAssistance, MAP_DATA, POINT_CONFIG

class MapPointTester:
    def __init__(self, root):
        self.root = root
        self.root.title("大地图点位助手 测试台")
        self.root.geometry("400x550")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        self.map_assistant = MapPointAssistance(self.root)
        self.is_running = False
        
        # UI 变量
        self.map_var = tk.StringVar(value="艾伦格 (Erangel)")
        self.category_vars = {} # 存放各个类别的 BooleanVar

        self.init_ui()

    def init_ui(self):
        tk.Label(self.root, text="战术点位记录 终端", fg="white", bg="#2C3E50", font=("Microsoft YaHei", 14, "bold")).pack(pady=10)
        
        if not self.map_assistant.monitor:
            tk.Label(self.root, text="⚠️ 尚未标定地图边界！", fg="#E74C3C", bg="#2C3E50", font=("Arial", 10, "bold")).pack()
        
        tk.Button(self.root, text="📏 1. 校准大地图边界 (框选正方形)", command=self.map_assistant.trigger_calibration, 
                  bg="#3498DB", fg="white", font=("Microsoft YaHei", 10)).pack(fill="x", padx=30, pady=10)

        # ================= 静态点位控制面板 =================
        panel = tk.LabelFrame(self.root, text=" 战术资源分布图层 ", bg="#34495E", fg="white", font=("Microsoft YaHei", 10))
        panel.pack(fill="x", padx=20, pady=5)
        
        # 选择地图下拉框
        map_frame = tk.Frame(panel, bg="#34495E")
        map_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(map_frame, text="当前地图:", bg="#34495E", fg="white").pack(side="left")
        map_selector = ttk.Combobox(map_frame, textvariable=self.map_var, values=list(MAP_DATA.keys()), state="readonly")
        map_selector.pack(side="right", expand=True, fill="x", padx=5)
        map_selector.bind("<<ComboboxSelected>>", self.on_display_changed)
        
        # 动态生成类别多选框
        for key, config in POINT_CONFIG.items():
            var = tk.BooleanVar(value=False)
            self.category_vars[key] = var
            chk = tk.Checkbutton(panel, text=config["name"], variable=var, bg="#34495E", fg=config["color"], 
                                 selectcolor="#2C3E50", activebackground="#34495E", command=self.on_display_changed)
            chk.pack(anchor="w", padx=20)

        # ================= 核心启停 =================
        self.btn_toggle = tk.Button(self.root, text="▶ 2. 开启大地图全局交互", command=self.toggle_system, 
                                    bg="#2ECC71", fg="white", font=("Microsoft YaHei", 11, "bold"))
        self.btn_toggle.pack(fill="x", padx=30, pady=15)
        
        tk.Label(self.root, text="提示: 勾选上方图层后，开启交互即可在游戏中显示静态点位。", fg="#BDC3C7", bg="#2C3E50", justify="left", font=("Arial", 9)).pack()

    def on_display_changed(self, event=None):
        """当用户切换地图或勾选类别时，通知核心模块刷新"""
        active_cats = {k for k, v in self.category_vars.items() if v.get()}
        self.map_assistant.update_static_display(self.map_var.get(), active_cats)

    def toggle_system(self):
        if not self.map_assistant.monitor:
            print("请先标定地图！")
            return

        self.is_running = not self.is_running
        self.map_assistant.set_enabled(self.is_running)
        
        # 启动时同步一次当前的静态显示状态
        if self.is_running:
            self.on_display_changed()
            self.btn_toggle.config(text="⏹ 停止全局交互与图层", bg="#E74C3C")
        else:
            self.btn_toggle.config(text="▶ 2. 开启大地图全局交互", bg="#2ECC71")

if __name__ == "__main__":
    root = tk.Tk()
    app = MapPointTester(root)
    root.mainloop()