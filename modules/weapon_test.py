import cv2
import numpy as np
import mss
import time
import threading
import os

class AutoWeaponDetectorTest:
    def __init__(self, screen_width, screen_height, templates_config, on_switch_callback):
        self.sw = screen_width
        self.sh = screen_height
        self.callback = on_switch_callback
        
        # 1. 坐标自适应换算 (基于 1920x1080)
        ref_w, ref_h = 1920.0, 1080.0
        box_left = int(self.sw * (890 / ref_w))
        box_top = int(self.sh * (925 / ref_h))
        box_width = int(self.sw * ((1030 - 890) / ref_w))
        box_height = int(self.sh * ((984 - 925) / ref_h))
        
        self.monitor = {
            "top": box_top,
            "left": box_left,
            "width": box_width,
            "height": box_height
        }
        
        print(f"[初始化] 屏幕分辨率: {self.sw}x{self.sh}")
        print(f"[初始化] 武器栏截取坐标: X={box_left}, Y={box_top}, 宽={box_width}, 高={box_height}")
        
        # 2. 加载模板
        self.templates = {}
        for weapon_name, path in templates_config.items():
            if not os.path.exists(path):
                print(f"[错误] 找不到模板文件: {path}")
                continue
                
            try:
                # 0 代表直接以单通道灰度模式读取
                img_gray = cv2.imread(path, 0)
                
                if img_gray is not None:
                    # 动态缩放
                    if self.sw != 1920 or self.sh != 1080:
                        scale_factor_x = self.sw / ref_w
                        scale_factor_y = self.sh / ref_h
                        new_size = (int(img_gray.shape[1] * scale_factor_x), int(img_gray.shape[0] * scale_factor_y))
                        img_gray = cv2.resize(img_gray, new_size, interpolation=cv2.INTER_LINEAR)
                    
                    # ======================================================
                    # 【新增魔法】：自动对比度拉伸！
                    # 即便你截的是暗灰色的武器，这行代码也会强制把它提亮成纯白色
                    img_gray = cv2.normalize(img_gray, None, 0, 255, cv2.NORM_MINMAX)
                    
                    # 提取边缘
                    img_edges = cv2.Canny(img_gray, 50, 150)
                    
                    # 【新增防呆】：检查提取出来的边缘是不是全黑的！
                    if cv2.countNonZero(img_edges) == 0:
                        print(f"[致命错误] ⚠️ {weapon_name} 提取不出任何边缘，模板全是黑的！请重新截图！")
                        continue # 跳过这个废弃模板
                    # ======================================================

                    self.templates[weapon_name] = img_edges
                    print(f"[加载成功] {weapon_name} 边缘模板已就绪，尺寸: {img_edges.shape}")
            except Exception as e:
                print(f"[加载失败] {path}: {e}")
        self.current_weapon = None
        self.is_running = False
        self.debug_snapshot_saved = False

    def start(self):
        self.is_running = True
        threading.Thread(target=self._detection_loop, daemon=True).start()
        print("\n=======================================")
        print("侦测已启动！请进入游戏并切换武器...")
        print("=======================================\n")

    def _detection_loop(self):
        with mss.MSS() as sct:
            while self.is_running:
                try:
                    screenshot = sct.grab(self.monitor)
                    frame = np.array(screenshot)
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
                    
                    # ======================================================
                    # 【全新升级】：提取实时游戏画面的边缘线框！
                    # 沙地、天空等平滑背景会全部变成死黑色，只有武器和草等边缘会变成白线
                    # ======================================================
                    live_edges = cv2.Canny(gray, 50, 150)
                    
                    # 调试功能：保存边缘图看看效果
                    if not self.debug_snapshot_saved:
                        cv2.imwrite("debug_1_gray.png", gray)
                        cv2.imwrite("debug_2_edges.png", live_edges)
                        print("\n[关键提示] 已生成 debug_2_edges.png，请查看轮廓是否清晰！\n")
                        self.debug_snapshot_saved = True

                    best_match = None
                    best_score = 0.0

                    for weapon_name, tpl in self.templates.items():
                        # 拿着线框图去匹配线框图
                        res = cv2.matchTemplate(live_edges, tpl, cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, _ = cv2.minMaxLoc(res)
                        
                        if max_val > best_score:
                            best_score = max_val
                            best_match = weapon_name

                    # 【注意】：边缘匹配的分数通常偏低（因为线框图90%以上是黑色）
                    # 原来 0.70 是及格，现在线框匹配，0.25~0.30 就是极高置信度了！
                    if best_score > 0.25: 
                        print(f"扫描到: {best_match} -> 线框得分: {best_score:.3f}")
                    
                except Exception as e:
                    print(f"运行出错: {e}")
                
                time.sleep(0.5)

# ================= 模拟主程序的调用 =================
def test_callback(weapon_name):
    print(f"\n🚀 【系统触发】 -> 自动切换至: {weapon_name} 助手！\n")

if __name__ == "__main__":
    # 1. 获取主显示器分辨率
    with mss.MSS() as sct:
        sw = sct.monitors[1]["width"]
        sh = sct.monitors[1]["height"]

    # 2. 配置你的模板路径 (请替换为你实际扣好的纯白图片的文件名)
    # 假设图片和这个脚本放在同一个文件夹里
    test_templates = {
        "VSS": "templates/vss.png", 
        "ROCKET": "templates/rocket.png",
        "CROSSBOW": "templates/crossbow.png",
        "GRENADE": "templates/grenade.png"
    }
    
    detector = AutoWeaponDetectorTest(sw, sh, test_templates, test_callback)
    detector.start()
    
    try:
        # 阻止主线程退出
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("测试结束。")