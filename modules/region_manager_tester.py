import tkinter as tk
from tkinter import ttk
import sys
import os
import ctypes

# 确保能导入 region_manager
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from region_manager import RegionManager

class RegionManagerTester:
    def __init__(self, root):
        self.root = root
        self.root.title("RegionManager 校准测试台")
        self.root.geometry("420x850")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#2C3E50")

        # 创建 RegionManager 实例
        self.rm = RegionManager(self.root, config_file="config.json")

        # 显示当前屏幕信息
        info_frame = tk.LabelFrame(self.root, text="屏幕信息", bg="#34495E", fg="white", font=("Arial", 10, "bold"))
        info_frame.pack(fill="x", padx=10, pady=10)
        tk.Label(info_frame, text=f"实际分辨率: {self.rm.real_w} x {self.rm.real_h}", bg="#34495E", fg="white").pack(anchor="w", padx=5, pady=2)
        tk.Label(info_frame, text=f"模板分辨率: 1920 x 1080 (固定)", bg="#34495E", fg="white").pack(anchor="w", padx=5, pady=2)

        # 调试模式开关按钮
        self.debug_btn = tk.Button(self.root, text="🟢 显示调试覆盖层 (OFF)", command=self.toggle_debug,
                                   bg="#E67E22", fg="white", font=("Microsoft YaHei", 10, "bold"))
        self.debug_btn.pack(fill="x", padx=20, pady=5)

        # 创建 Notepad 风格的标签页（区域校准 / 比例尺校准）
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # 区域校准页面
        self.region_frame = tk.Frame(self.notebook, bg="#2C3E50")
        self.notebook.add(self.region_frame, text="📏 区域校准")

        # 比例尺校准页面
        self.scale_frame = tk.Frame(self.notebook, bg="#2C3E50")
        self.notebook.add(self.scale_frame, text="📐 比例尺校准")

        self._build_region_buttons()
        self._build_scale_buttons()

        # 状态栏显示当前校准状态
        self.status_var = tk.StringVar(value="就绪")
        status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W,
                              bg="#34495E", fg="#BDC3C7")
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _build_region_buttons(self):
        """创建所有区域校准按钮"""
        regions = [
            ("🔭 倍镜区域 (scope_region)", "scope_region"),
            ("🔫 武器区域 (weapon_region)", "weapon_region"),
            ("🧍 姿态区域 (stance_region)", "stance_region"),
            ("🗺️ 小地图区域 (minimap_region)", "minimap_region"),
            ("🌍 大地图区域 (largemap_region)", "largemap_region"),
            ("📈 仰角区域 (elevation_region)", "elevation_region"),
            ("🧭 指南针区域 (compass_region)", "compass_region"),
            ("🎯 准星区域 (crosshair_region)", "crosshair_region"),
            # === 武器1区域 ===
            ("🔫 武器1 名称区域 (weapon1_name_region)", "weapon1_name_region"),
            ("🔢 武器1 编号区域 (weapon1_number_region)", "weapon1_number_region"),
            ("🔍 武器1 倍镜区域 (weapon1_scope_region)", "weapon1_scope_region"),
            ("✊ 武器1 握把区域 (weapon1_grip_region)", "weapon1_grip_region"),
            ("🔫 武器1 枪口区域 (weapon1_muzzle_region)", "weapon1_muzzle_region"),
            ("🪚 武器1 枪托区域 (weapon1_stock_region)", "weapon1_stock_region"),

            # === 武器2区域 ===
            ("🔫 武器2 名称区域 (weapon2_name_region)", "weapon2_name_region"),
            ("🔢 武器2 编号区域 (weapon2_number_region)", "weapon2_number_region"),
            ("🔍 武器2 倍镜区域 (weapon2_scope_region)", "weapon2_scope_region"),
            ("✊ 武器2 握把区域 (weapon2_grip_region)", "weapon2_grip_region"),
            ("🔫 武器2 枪口区域 (weapon2_muzzle_region)", "weapon2_muzzle_region"),
            ("🪚 武器2 枪托区域 (weapon2_stock_region)", "weapon2_stock_region"),
        ]

        for idx, (label, region_name) in enumerate(regions):
            # 显示当前区域是否已校准（通过 real_regions 是否存在该键）
            rect = self.rm.get_real_region(region_name)
            if rect:
                status_text = f"✅ 已校准: {rect['width']}x{rect['height']}"
                status_color = "#2ECC71"
            else:
                status_text = "❌ 未校准"
                status_color = "#E74C3C"

            frame = tk.Frame(self.region_frame, bg="#2C3E50")
            frame.pack(fill="x", padx=10, pady=5)

            btn = tk.Button(frame, text=label, command=lambda r=region_name: self.calibrate_region(r),
                            bg="#3498DB", fg="white", font=("Microsoft YaHei", 9), width=30)
            btn.pack(side=tk.LEFT, padx=5)

            status_label = tk.Label(frame, text=status_text, bg="#2C3E50", fg=status_color, font=("Arial", 8))
            status_label.pack(side=tk.RIGHT, padx=5)

    def _build_scale_buttons(self):
        """创建比例尺校准按钮"""
        scales = [
            ("🗺️ 小地图 100米 比例尺 (minimap_100m_px)", "minimap_100m_px"),
            ("🌍 大地图 1公里 比例尺 (largemap_1km_px)", "largemap_1km_px"),
        ]

        for label, scale_name in scales:
            # 显示当前比例尺值
            scale_val = self.rm.get_real_scale(scale_name)
            if scale_val:
                status_text = f"✅ 已校准: {scale_val:.1f} px"
                status_color = "#2ECC71"
            else:
                status_text = "❌ 未校准"
                status_color = "#E74C3C"

            frame = tk.Frame(self.scale_frame, bg="#2C3E50")
            frame.pack(fill="x", padx=10, pady=5)

            btn = tk.Button(frame, text=label, command=lambda s=scale_name: self.calibrate_scale(s),
                            bg="#9B59B6", fg="white", font=("Microsoft YaHei", 9), width=25)
            btn.pack(side=tk.LEFT, padx=5)

            status_label = tk.Label(frame, text=status_text, bg="#2C3E50", fg=status_color, font=("Arial", 8))
            status_label.pack(side=tk.RIGHT, padx=5)

    def toggle_debug(self):
        """切换调试覆盖层显示"""
        new_state = not self.rm.show_debug
        self.rm.set_debug_mode(new_state)
        if new_state:
            self.debug_btn.config(text="🔴 隐藏调试覆盖层 (ON)", bg="#2ECC71")
        else:
            self.debug_btn.config(text="🟢 显示调试覆盖层 (OFF)", bg="#E67E22")

    def calibrate_region(self, region_name):
        """启动区域校准，并在状态栏提示"""
        self.status_var.set(f"正在校准 {region_name}，请在屏幕上框选区域...")
        self.root.update()
        self.rm.calibrate_region(region_name)
        self.status_var.set(f"✓ {region_name} 校准完成 (已保存到 config.json)")
        self.refresh_ui()

    def calibrate_scale(self, scale_name):
        """启动比例尺校准，并在状态栏提示"""
        self.status_var.set(f"正在校准 {scale_name}，请画一条水平/垂直线段表示实际距离...")
        self.root.update()
        self.rm.calibrate_scale(scale_name)
        self.status_var.set(f"✓ {scale_name} 校准完成 (已保存到 config.json)")
        self.refresh_ui()

    def refresh_ui(self):
        """刷新按钮状态（重新读取区域和比例尺）"""
        for widget in self.region_frame.winfo_children():
            widget.destroy()
        for widget in self.scale_frame.winfo_children():
            widget.destroy()
        self._build_region_buttons()
        self._build_scale_buttons()

    def on_closing(self):
        """退出时关闭调试覆盖层并销毁窗口"""
        self.rm.set_debug_mode(False)
        self.root.destroy()

if __name__ == "__main__":
    # 设置 DPI 感知，获取真实物理分辨率
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except:
        pass
    root = tk.Tk()
    app = RegionManagerTester(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()