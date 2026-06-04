import tkinter as tk
import sys
import os

# 确保能导入同级目录下的模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from region_manager import RegionManager
from minimap_radar import MinimapRadarModule

def main():
    # 创建根窗口（必须，但会被隐藏）
    root = tk.Tk()
    root.withdraw()

    # 1. 初始化区域管理器（会自动加载 config.json 中的小地图区域和比例尺）
    rm = RegionManager(root, config_file="config.json")

    # 2. 创建雷达模块
    radar = MinimapRadarModule(root, rm)

    # 3. 启用雷达（启动视觉线程）并显示 overlay
    radar.set_enabled(True)
    radar.set_display(True)

    print("=" * 50)
    print("小地图测距雷达已启动")
    print("请确保 config.json 中已经校准好 'minimap_region'")
    print("同时确保 templates/pnt/ 文件夹下存在标点模板图片")
    print("按 Ctrl+C 或关闭此控制台窗口退出")
    print("=" * 50)

    # 可选：打印当前小地图区域信息（用于调试）
    minimap = rm.get_real_region("minimap_region")
    if minimap:
        print(f"[信息] 当前小地图区域: left={minimap['left']}, top={minimap['top']}, "
              f"width={minimap['width']}, height={minimap['height']}")
    else:
        print("[警告] 未找到小地图区域，请先用 RegionManager 校准 minimap_region")

    scale_100m = rm.get_real_scale("minimap_100m_px")
    if scale_100m:
        print(f"[信息] 100米对应的像素距离: {scale_100m:.2f} px (仅参考，实际测距使用固定700米算法)")
    else:
        print("[信息] 未找到 minimap_100m_px 比例尺，将使用默认 700 米算法")

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        radar.set_enabled(False)
        root.destroy()

if __name__ == "__main__":
    main()