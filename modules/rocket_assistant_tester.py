import tkinter as tk
from region_manager import RegionManager
from minimap_radar import MinimapRadarModule
from rocket_assistant import RocketAssistant

class RealRocketTester:
    def __init__(self, root):
        self.root = root
        self.root.title("火箭筒真机集成测试台")
        self.root.geometry("380x400")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        # 初始化区域管理器（负责加载 config.json 中的小地图区域）
        self.region_manager = RegionManager(self.root, config_file="config.json")

        # 获取实际屏幕分辨率
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()

        # 1. 创建小地图雷达模块（不自动启动，由火箭筒助手控制启停）
        self.minimap = MinimapRadarModule(self.root, self.region_manager, config_file="config.json")

        # 2. 创建火箭筒助手模块（内部会控制小地图雷达的启停）
        self.rocket = RocketAssistant(self.root, self.screen_width, self.screen_height,
                                      self.minimap, fps=30, config_file="config.json")

        # UI 状态
        self.is_running = False
        self.show_sensor_debug = True   # 是否显示小地图识别图层（圆框+距离）

        self.init_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def init_ui(self):
        tk.Label(self.root, text="全链路火箭筒系统测试台", fg="white", bg="#2C3E50",
                 font=("Microsoft YaHei", 14, "bold")).pack(pady=10)

        # 提示信息
        info_frame = tk.Frame(self.root, bg="#2C3E50")
        info_frame.pack(pady=5)
        tk.Label(info_frame, text="使用前请确保 config.json 中已配置：", fg="#BDC3C7", bg="#2C3E50").pack()
        tk.Label(info_frame, text="1. minimap_region（小地图区域）", fg="#BDC3C7", bg="#2C3E50").pack()
        tk.Label(info_frame, text="2. rocket_config（弹道标定数据）", fg="#BDC3C7", bg="#2C3E50").pack()

        # 控制按钮
        self.btn_debug = tk.Button(self.root, text="隐藏小地图识别图层", command=self.toggle_sensor_debug,
                                   bg="#E67E22", fg="white", font=("Microsoft YaHei", 10))
        self.btn_debug.pack(fill="x", padx=30, pady=5)

        self.btn_toggle = tk.Button(self.root, text="▶ 启动侦测与动态标尺", command=self.toggle_system,
                                    bg="#2ECC71", fg="white", font=("Microsoft YaHei", 16, "bold"))
        self.btn_toggle.pack(fill="x", padx=20, pady=20)

        # 状态标签
        self.status_label = tk.Label(self.root, text="状态：未启动", fg="#F1C40F", bg="#2C3E50")
        self.status_label.pack(pady=5)

    def toggle_sensor_debug(self):
        """切换小地图雷达的显示图层（仅当雷达已启用时有效）"""
        self.show_sensor_debug = not self.show_sensor_debug
        self.minimap.set_display(self.show_sensor_debug)
        if self.show_sensor_debug:
            self.btn_debug.config(text="隐藏小地图识别图层", bg="#E67E22")
        else:
            self.btn_debug.config(text="显示小地图识别图层", bg="#7F8C8D")

    def toggle_system(self):
        """启动/停止整个火箭筒辅助系统"""
        self.is_running = not self.is_running
        # 火箭筒助手的 enable_module 会自动启动/停止小地图雷达
        self.rocket.enable_module(self.is_running)

        if self.is_running:
            self.btn_toggle.config(text="⏹ 停止侦测与动态标尺", bg="#E74C3C")
            self.status_label.config(text="状态：运行中", fg="#2ECC71")
            # 启动时，将小地图图层的显示状态设为用户当前选择的显示模式
            self.minimap.set_display(self.show_sensor_debug)
        else:
            self.btn_toggle.config(text="▶ 启动侦测与动态标尺", bg="#2ECC71")
            self.status_label.config(text="状态：已停止", fg="#F1C40F")
            # 停止时，清空小地图图层显示
            self.minimap.set_display(False)

    def on_closing(self):
        """安全退出，释放资源"""
        self.rocket.enable_module(False)   # 会同时停止小地图雷达
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = RealRocketTester(root)
    root.mainloop()