import math

class MapRangingModule:
    """
    大地图战术测距插件
    依赖于 MapCoreModule。负责接收点击事件，绘制连线，并计算迫击炮/大炮所需的物理距离与方位角。
    """
    def __init__(self, map_core, default_map_size=8000.0):
        # 接收并保存核心模块的引用
        self.core = map_core
        self.map_real_size = default_map_size
        
        self.measure_points = []
        
        # 将自己的逻辑函数“挂载”到核心模块的事件监听器上
        self.core.on_left_click_callbacks.append(self._on_map_clicked)
        self.core.on_right_click_callbacks.append(self._on_map_right_clicked)

    def _on_map_clicked(self, x, y):
        """当核心模块接收到左键点击时，此函数被触发"""
        if len(self.measure_points) >= 2:
            self.measure_points.clear()
            
        self.measure_points.append((x, y))
        self._render_ui()

    def _on_map_right_clicked(self, event):
        """当核心模块接收到右键点击时，此函数被触发"""
        self.measure_points.clear()
        self._render_ui()

    def _calculate_geo_data(self, pt1, pt2):
        """使用核心模块提供的比例尺进行物理换算"""
        monitor = self.core.monitor
        if not monitor: return 0, 0
        
        px_dist = math.sqrt((pt2[0] - pt1[0])**2 + (pt2[1] - pt1[1])**2)
        real_dist = (px_dist / monitor["side"]) * self.map_real_size
        
        dx = pt2[0] - pt1[0]
        dy = -(pt2[1] - pt1[1]) # Y轴反转
        
        angle = math.degrees(math.atan2(dx, dy))
        if angle < 0: angle += 360
            
        return real_dist, angle

    def _render_ui(self):
        """在核心画板上绘制测距UI"""
        # 注意：使用特定的 tag ("ranging_ui") 以免删掉核心模块的校准画面
        canvas = self.core.canvas
        canvas.delete("ranging_ui")
        
        if len(self.measure_points) > 0:
            for i, (x, y) in enumerate(self.measure_points):
                color = "#3498DB" if i == 0 else "#E74C3C" 
                canvas.create_oval(x-4, y-4, x+4, y+4, fill=color, outline="white", tags="ranging_ui")
                
            if len(self.measure_points) == 2:
                p1, p2 = self.measure_points[0], self.measure_points[1]
                canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill="white", width=2, dash=(5, 5), tags="ranging_ui")
                
                dist, angle = self._calculate_geo_data(p1, p2)
                mid_x, mid_y = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
                
                text_info = f"{dist:.0f}m | {angle:.1f}°"
                canvas.create_rectangle(mid_x+10, mid_y-10, mid_x+120, mid_y+15, fill="#111111", outline="#E74C3C", tags="ranging_ui")
                canvas.create_text(mid_x+65, mid_y+2, text=text_info, fill="#00FF00", font=("Consolas", 11, "bold"), tags="ranging_ui")