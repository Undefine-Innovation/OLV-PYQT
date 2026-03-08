from live2d.utils.canvas import Canvas
from live2d.utils.image import Image
import live2d.v3 as live2d
if live2d.LIVE2D_VERSION == 3:
    from live2d.v3.params import StandardParams
elif live2d.LIVE2D_VERSION == 2:
    from live2d.v2.params import StandardParams

import math
import os
from PyQt5.QtCore import Qt, QTimer, pyqtSlot, QPoint
from PyQt5.QtWidgets import (
    QOpenGLWidget, QLabel, QVBoxLayout, QWidget,
    QSizePolicy, QPushButton, QStackedWidget, QHBoxLayout, QSlider
)
from PyQt5.QtGui import QPalette, QSurfaceFormat
import OpenGL.GL as gl
from loguru import logger

from .chat_floating_window import ChatFloatingWindow
from .qml_settings_page import QMLSettingsPage
from OQController.ws_controller import WSController
# 导入音频状态管理器
from OQController.audio_state_manager import get_audio_state_manager

# 导入配置管理器
try:
    from OQConfig.config_manager import get_config_manager
    config_manager = get_config_manager()
except ImportError as e:
    logger.warning(f"无法导入配置管理器: {e}")
    config_manager = None


class Live2DCanvas(QOpenGLWidget):
    
    def __init__(self, parent=None, controller=None, main_window=None):
        super().__init__(parent)
        self.parent_window = main_window if main_window else parent  # 用于窗口操作
        self.stacked_widget = parent  # 用于页面切换
        self.controller = controller
        self.timer_id = None
        self.is_rendering = True
        
        # 音频状态管理器
        self.audio_state_manager = get_audio_state_manager()
        
        # 增强的透明化设置
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)
        
        # 设置OpenGL格式以支持alpha通道
        _format = QSurfaceFormat()
        _format.setAlphaBufferSize(8)
        _format.setSamples(4)  # 抗锯齿
        self.setFormat(_format)
        
        # 窗口模式相关
        self.window_mode = 1  # 0: 沉浸模式, 1: 窗口模式, 2: 桌宠模式
        self.drag_position = QPoint()
        
        self.model = None
        self.canvas = None
        self.radius_per_frame = math.pi * 0.5 / 120
        self.total_radius = 0

        self.background = None
        self.background_type = 0
        self.background_theme = 0
        self.custom_wallpaper_path = ""
        self.default_backgrounds = [
            "Resources/RING.png",        # 默认背景
            "Resources/NIGHT.jpeg",      # 深色主题
            "Resources/MOON.jpeg",       # 浅色主题
            "Resources/COMPUTER.jpeg",   # 蓝色科技
            "Resources/GRASS.jpeg",      # 绿色自然
            "Resources/CITYROOM.jpeg",   # 城市房间
            "Resources/CLASSROOM.jpeg",  # 教室场景
            "Resources/INTERIOROOM.jpeg",# 室内场景
            "Resources/VALLEY.jpeg",     # 山谷风景
        ]

        self.mouth_control_enabled = False
        self.mouth_timer = None
        self.mouth_open_state = False
        self.mouth_cycle_time = 100

        self.chat_window = None

        # 人物控制属性
        self.character_scale = 1.0  # 缩放比例，默认1.0
        self.character_x_offset = 0.0  # X轴偏移
        self.character_y_offset = 0.0  # Y轴偏移

        # 对话标签
        self.dialog_label = QLabel("你好，我是AI助手！", self)
        self.dialog_label.setWordWrap(True)
        self.dialog_label.setStyleSheet("""
            background-color: rgba(0, 0, 0, 180);
            color: white;
            font-size: 24px;
            padding: 50px;
            border-radius: 15px;
        """)
        self.dialog_label.setAlignment(Qt.AlignCenter)
        self.dialog_label.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Minimum
        )
        # 设置对话框可点击
        self.dialog_label.mousePressEvent = self.on_dialog_clicked
        
        # 打字机效果相关属性
        self.typewriter_timer = QTimer()
        self.typewriter_timer.timeout.connect(self.update_typewriter_text)
        self.typewriter_full_text = ""
        self.typewriter_current_index = 0
        self.typewriter_speed = 50  # 打字速度（毫秒）
        self.dialog_hide_timer = QTimer()
        self.dialog_hide_timer.timeout.connect(self.hide_dialog)
        self.dialog_hide_timer.setSingleShot(True)

        # 设置按钮
        self.settings_button = QPushButton("⚙️", self)
        self.settings_button.setFixedSize(60, 60)
        self.settings_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 180);
                border-radius: 20px;
                color: white;
                font-size: 40px;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 180);
            }
        """)
        self.settings_button.clicked.connect(self.show_settings)
        self.settings_button.move(10, 10)

        # 聊天按钮
        self.chat_button = QPushButton("💬", self)
        self.chat_button.setFixedSize(60, 60)
        self.chat_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 180);
                border-radius: 20px;
                color: white;
                font-size: 40px;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 180);
            }
        """)
        self.chat_button.clicked.connect(self.toggle_chat_window)
        self.chat_button.move(10, 80)

        # 人物控制切换按钮
        self.character_control_button = QPushButton("🎮", self)
        self.character_control_button.setFixedSize(60, 60)
        self.character_control_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 180);
                border-radius: 20px;
                color: white;
                font-size: 40px;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 220);
            }
        """)
        self.character_control_button.clicked.connect(self.toggle_character_control_panel)
        self.character_control_button.move(10, 150)

        # 桌宠模式专用按钮
        self.create_desktop_pet_buttons()

        layout = QVBoxLayout(self)
        layout.addWidget(self.dialog_label, alignment=Qt.AlignHCenter | Qt.AlignBottom)
        self.setLayout(layout)
        
        # 创建人物控制面板
        self.create_character_control_panel()
        
        if self.controller:
            self.setup_controller_connections()

    def create_desktop_pet_buttons(self):
        """创建桌宠模式专用的控制按钮"""
        # 关闭按钮
        self.close_button = QPushButton("✕", self)
        self.close_button.setFixedSize(30, 30)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 0, 0, 180);
                border-radius: 15px;
                color: white;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 0, 0, 220);
            }
        """)
        self.close_button.clicked.connect(self.close_application)
        self.close_button.hide()  # 默认隐藏

        # 最小化按钮
        self.minimize_button = QPushButton("−", self)
        self.minimize_button.setFixedSize(30, 30)
        self.minimize_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(100, 100, 100, 180);
                border-radius: 15px;
                color: white;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(100, 100, 100, 220);
            }
        """)
        self.minimize_button.clicked.connect(self.minimize_window)
        self.minimize_button.hide()  # 默认隐藏

    def create_character_control_panel(self):
        """创建人物控制面板"""
        # 人物控制面板容器
        self.character_control_widget = QWidget(self)
        self.character_control_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 150);
                border-radius: 10px;
                padding: 10px;
            }
        """)
        self.character_control_widget.setFixedSize(200, 150)
        
        # 创建布局
        control_layout = QVBoxLayout(self.character_control_widget)
        control_layout.setSpacing(5)
        
        # 滑块样式
        slider_style = """
            QSlider::groove:horizontal {
                border: 1px solid #999999;
                height: 8px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #B1B1B1, stop:1 #c4c4c4);
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #b4b4b4, stop:1 #8f8f8f);
                border: 1px solid #5c5c5c;
                width: 18px;
                margin: -2px 0;
                border-radius: 9px;
            }
        """
        
        # 标签样式
        label_style = "color: white; font-size: 12px; font-family: 'Microsoft YaHei', 'SimHei', Arial, sans-serif;"
        
        # 缩放控制 - 水平布局
        scale_layout = QHBoxLayout()
        scale_label = QLabel("👀", self.character_control_widget)
        scale_label.setStyleSheet(label_style)
        scale_label.setFixedWidth(40)
        self.scale_slider = QSlider(Qt.Horizontal, self.character_control_widget)
        self.scale_slider.setMinimum(50)
        self.scale_slider.setMaximum(200)
        self.scale_slider.setValue(100)
        self.scale_slider.setStyleSheet(slider_style)
        self.scale_slider.valueChanged.connect(self.on_scale_changed)
        scale_layout.addWidget(scale_label)
        scale_layout.addWidget(self.scale_slider)
        
        # X轴位置控制 - 水平布局
        x_layout = QHBoxLayout()
        x_label = QLabel("X", self.character_control_widget)
        x_label.setStyleSheet(label_style)
        x_label.setFixedWidth(40)
        self.x_slider = QSlider(Qt.Horizontal, self.character_control_widget)
        self.x_slider.setMinimum(-100)
        self.x_slider.setMaximum(100)
        self.x_slider.setValue(0)
        self.x_slider.setStyleSheet(slider_style)
        self.x_slider.valueChanged.connect(self.on_x_pos_changed)
        x_layout.addWidget(x_label)
        x_layout.addWidget(self.x_slider)
        
        # Y轴位置控制 - 水平布局
        y_layout = QHBoxLayout()
        y_label = QLabel("Y", self.character_control_widget)
        y_label.setStyleSheet(label_style)
        y_label.setFixedWidth(40)
        self.y_slider = QSlider(Qt.Horizontal, self.character_control_widget)
        self.y_slider.setMinimum(-100)
        self.y_slider.setMaximum(100)
        self.y_slider.setValue(0)
        self.y_slider.setStyleSheet(slider_style)
        self.y_slider.valueChanged.connect(self.on_y_pos_changed)
        y_layout.addWidget(y_label)
        y_layout.addWidget(self.y_slider)
        
        # 添加布局到主布局
        control_layout.addLayout(scale_layout)
        control_layout.addLayout(x_layout)
        control_layout.addLayout(y_layout)
        
        # 设置面板位置（按钮下方）
        self.character_control_widget.move(10, 220)
        self.character_control_widget.hide()  # 初始状态为隐藏

    def on_scale_changed(self, value):
        """处理缩放滑块变化"""
        self.character_scale = value / 100.0  # 转换为0.5-2.0的范围
        logger.info(f"[Live2D] 人物缩放改变: {self.character_scale}")
        self.update()  # 触发重绘

    def on_x_pos_changed(self, value):
        """处理X轴位置滑块变化"""
        self.character_x_offset = value
        logger.info(f"[Live2D] 人物X轴位置改变: {self.character_x_offset}")
        self.update()  # 触发重绘

    def on_y_pos_changed(self, value):
        """处理Y轴位置滑块变化"""
        self.character_y_offset = value
        logger.info(f"[Live2D] 人物Y轴位置改变: {self.character_y_offset}")
        self.update()  # 触发重绘
    
    def toggle_character_control_panel(self):
        """切换人物控制面板的显示/隐藏"""
        if self.character_control_widget.isVisible():
            self.character_control_widget.hide()
        else:
            self.character_control_widget.show()

    def close_application(self):
        """关闭应用程序"""
        if self.parent_window:
            self.parent_window.close()

    def minimize_window(self):
        """最小化窗口"""
        if self.parent_window:
            self.parent_window.showMinimized()

    def setup_window_mode_connections(self, settings_slot):
        """设置窗口模式相关的信号连接"""
        if settings_slot:
            settings_slot.windowModeChanged.connect(self.on_window_mode_changed)
            logger.info("[Live2D] 已连接窗口模式设置信号")

    @pyqtSlot(int)
    def on_window_mode_changed(self, mode_index):
        """窗口模式改变处理"""
        logger.info(f"[Live2D] 窗口模式改变: {mode_index}")
        self.window_mode = mode_index
        self.apply_window_mode()

    def apply_window_mode(self):
        """应用窗口模式"""
        if not self.parent_window:
            return
            
        if self.window_mode == 0:  # 沉浸模式
            self.apply_immersive_mode()
        elif self.window_mode == 1:  # 窗口模式
            self.apply_window_mode_normal()
        elif self.window_mode == 2:  # 桌宠模式
            self.apply_desktop_pet_mode()

    def apply_immersive_mode(self):
        """应用沉浸模式：无边框最大化"""
        logger.info("[Live2D] 切换到沉浸模式")
        self.parent_window.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.parent_window.showMaximized()
        
        # 隐藏桌宠模式按钮
        self.close_button.hide()
        self.minimize_button.hide()
        
        # 显示普通按钮
        self.settings_button.show()
        self.chat_button.show()
        
        # 显示背景
        self.update_background_visibility(True)

    def apply_window_mode_normal(self):
        """应用普通窗口模式"""
        logger.info("[Live2D] 切换到窗口模式")
        self.parent_window.setWindowFlags(Qt.Window)
        
        # 恢复窗口可调整大小 - 取消固定大小限制
        self.parent_window.setMinimumSize(0, 0)
        self.parent_window.setMaximumSize(16777215, 16777215)
        
        self.parent_window.resize(800, 600)
        self.parent_window.show()
        
        # 隐藏桌宠模式按钮
        self.close_button.hide()
        self.minimize_button.hide()
        
        # 显示普通按钮
        self.settings_button.show()
        self.chat_button.show()
        
        # 显示背景
        self.update_background_visibility(True)

    def apply_desktop_pet_mode(self):
        """应用桌宠模式：固定大小、透明背景、可拖拽"""
        logger.info("[Live2D] 切换到桌宠模式")
        
        # 设置窗口属性：无边框、置顶、透明背景
        self.parent_window.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint | 
            Qt.Tool
        )
        
        # 设置透明背景属性
        self.parent_window.setAttribute(Qt.WA_TranslucentBackground, True)
        
        # 设置固定大小
        pet_size = 800
        self.parent_window.setFixedSize(pet_size, pet_size)
        
        # 显示桌宠模式按钮
        self.close_button.show()
        self.minimize_button.show()
        
        # 调整按钮位置
        self.close_button.move(pet_size - 35, 5)
        self.minimize_button.move(pet_size - 70, 5)
        
        # 调整普通按钮位置和大小
        self.settings_button.setFixedSize(40, 40)
        self.chat_button.setFixedSize(40, 40)
        self.settings_button.move(5, 5)
        self.chat_button.move(5, 50)
        
        # 隐藏背景
        self.update_background_visibility(False)
        
        self.parent_window.show()

    def update_background_visibility(self, visible):
        """更新背景显示状态"""
        if visible:
            self.update_background()
        else:
            self.background = None

    def mousePressEvent(self, event):
        """鼠标按下事件 - 处理拖拽和点击检测"""
        if event.button() == Qt.LeftButton:
            # 桌宠模式下记录拖拽起始位置
            if self.window_mode == 2:  # 桌宠模式
                self.drag_position = event.globalPos() - self.parent_window.frameGeometry().topLeft()
            
            # Live2D模型点击检测
            if self.model:
                x, y = event.x(), event.y()
                logger.info(f"[Live2D] 鼠标点击位置: ({x}, {y})")
                
                try:
                    if hasattr(self.model, 'HitTest'):
                        if self.model.HitTest("Body", x, y):
                            logger.info("[Live2D] 检测到点击身体区域 - Body被点击了")
                        elif self.model.HitTest("Head", x, y):
                            logger.info("[Live2D] 检测到点击头部区域 - Head被点击了")
                        elif self.model.HitTest("Face", x, y):
                            logger.info("[Live2D] 检测到点击脸部区域 - Face被点击了")
                        else:
                            logger.info("[Live2D] 点击了空白区域")
                    
                    if hasattr(self.model, 'HitPart'):
                        hit_parts = self.model.HitPart(x, y)
                        if hit_parts:
                            logger.info(f"[Live2D] 检测到点击部件: {hit_parts}")
                            if "Part01" in hit_parts:
                                logger.info("[Live2D] 检测到点击Part01 - Part01被点击了")
                                
                except Exception as e:
                    logger.error(f"[Live2D] 点击检测失败: {e}")
                    import traceback
                    logger.error(f"[Live2D] 详细错误信息: {traceback.format_exc()}")
        
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 处理桌宠模式拖拽"""
        if (event.buttons() == Qt.LeftButton and 
            self.window_mode == 2 and  # 桌宠模式
            hasattr(self, 'drag_position')):
            
            # 移动窗口
            self.parent_window.move(event.globalPos() - self.drag_position)
        
        super().mouseMoveEvent(event)

    def setup_background_connections(self, settings_slot):
        if settings_slot:
            settings_slot.backgroundTypeChanged.connect(self.on_background_type_changed)
            settings_slot.backgroundThemeChanged.connect(self.on_background_theme_changed)
            settings_slot.wallpaperFileSelected.connect(self.on_wallpaper_file_selected)
            settings_slot.wallpaperPathChanged.connect(self.on_wallpaper_path_changed)
            logger.info("[Live2D] 已连接背景设置信号")

    @pyqtSlot(int)
    def on_background_type_changed(self, bg_type):
        logger.info(f"[Live2D] 背景类型改变: {bg_type}")
        self.background_type = bg_type
        self.update_background()

    @pyqtSlot(int)
    def on_background_theme_changed(self, theme_index):
        logger.info(f"[Live2D] 背景主题改变: {theme_index}")
        self.background_theme = theme_index
        if self.background_type == 0:
            self.update_background()

    @pyqtSlot(str)
    def on_wallpaper_file_selected(self, file_path):
        logger.info(f"[Live2D] 壁纸文件选择: {file_path}")
        self.custom_wallpaper_path = file_path
        if self.background_type == 1:
            self.update_background()

    @pyqtSlot(str)
    def on_wallpaper_path_changed(self, wallpaper_path):
        logger.info(f"[Live2D] 壁纸路径改变: {wallpaper_path}")
        self.custom_wallpaper_path = wallpaper_path
        if self.background_type == 1:
            self.update_background()

    def update_background(self):
        # 桌宠模式下不显示背景
        if self.window_mode == 2:
            self.background = None
            return
            
        try:
            background_path = None
            
            if self.background_type == 0:
                if self.background_theme < len(self.default_backgrounds):
                    background_path = self.default_backgrounds[self.background_theme]
                else:
                    background_path = self.default_backgrounds[0]
            elif self.background_type == 1:
                if self.custom_wallpaper_path and os.path.exists(self.custom_wallpaper_path):
                    background_path = self.custom_wallpaper_path
                else:
                    logger.warning(f"[Live2D] 自定义壁纸路径无效: {self.custom_wallpaper_path}")
                    background_path = self.default_backgrounds[0]
            
            if background_path:
                if not os.path.isabs(background_path):
                    background_path = os.path.join(os.getcwd(), background_path)
                
                if os.path.exists(background_path):
                    self.background = Image(background_path)
                    logger.info(f"[Live2D] 背景更新成功: {background_path}")
                else:
                    logger.error(f"[Live2D] 背景文件不存在: {background_path}")
                    self.background = None
            else:
                self.background = None
                logger.info("[Live2D] 背景设置为空")
            
        except Exception as e:
            logger.error(f"[Live2D] 更新背景失败: {e}")
            import traceback
            logger.error(f"[Live2D] 详细错误信息: {traceback.format_exc()}")
            self.background = None

    def setup_controller_connections(self):
        self.controller.expression_changed.connect(self.on_expression_changed)
        self.controller.ai_response.connect(self.show_dialog)

        # 直接连接来自 WebSocket 控制器的音频与字幕信号
        if hasattr(self.controller, 'audio_playback_started') and hasattr(self.controller, 'audio_playback_finished'):
            self.controller.audio_playback_started.connect(self.on_audio_playback_started)
            self.controller.audio_playback_finished.connect(self.on_audio_playback_finished)

            # 连接字幕信号
            if hasattr(self.controller, 'subtitle_display_requested'):
                self.controller.subtitle_display_requested.connect(self.on_subtitle_display_requested)
            if hasattr(self.controller, 'subtitle_clear_requested'):
                self.controller.subtitle_clear_requested.connect(self.on_subtitle_clear_requested)

            # 连接到音频状态管理器以驱动嘴巴控制
            self.controller.audio_playback_started.connect(self.audio_state_manager.on_ai_speech_started)
            self.controller.audio_playback_finished.connect(self.audio_state_manager.on_ai_speech_finished)

            logger.info("[Live2D] 已连接WS控制器的音频与字幕信号")
        else:
            logger.warning("[Live2D] WS控制器未提供音频或字幕信号，嘴巴自动控制可能无法工作")
        
    def on_audio_playback_started(self):
        logger.info("[Live2D] 音频播放开始，自动开启嘴巴控制")
        self.start_mouth_control()
        
    def on_audio_playback_finished(self):
        logger.info("[Live2D] 音频播放结束，自动关闭嘴巴控制")
        self.stop_mouth_control()
    
    def on_subtitle_display_requested(self, subtitle_text, sequence_id):
        """处理字幕显示请求"""
        logger.info(f"[Live2D] 字幕显示请求: seq={sequence_id}, text='{subtitle_text[:30]}{'...' if len(subtitle_text) > 30 else ''}'")
        # 显示字幕到对话框
        self.show_dialog(subtitle_text)

    def on_subtitle_clear_requested(self, sequence_id):
        """处理字幕清除请求"""
        logger.info(f"[Live2D] 字幕清除请求: seq={sequence_id}")
        # 隐藏对话框
        self.hide_dialog()
        
    def start_mouth_control(self):
        logger.info(f"[Debug] 尝试启动嘴巴控制 - enabled: {self.mouth_control_enabled}, model: {self.model}")
        if not self.mouth_control_enabled and self.model:
            self.mouth_control_enabled = True
            self.mouth_open_state = False
            self.mouth_timer = QTimer()
            self.mouth_timer.timeout.connect(self.toggle_mouth)
            self.mouth_timer.start(self.mouth_cycle_time)
            logger.info("[Live2D] 开始嘴巴控制循环")
        else:
            logger.warning(f"[Debug] 无法启动嘴巴控制 - enabled: {self.mouth_control_enabled}, model: {self.model}")
            
    def stop_mouth_control(self):
        if self.mouth_control_enabled:
            self.mouth_control_enabled = False
            if self.mouth_timer:
                self.mouth_timer.stop()
                self.mouth_timer = None
            if self.model:
                self.set_mouth_open(0.0)
            
    def toggle_mouth_control(self):
        if self.mouth_control_enabled:
            self.stop_mouth_control()
        else:
            self.start_mouth_control()
            
    def toggle_mouth(self):
        if not self.model:
            logger.warning("[Debug] 模型未加载，无法切换嘴巴状态")
            return
            
        self.mouth_open_state = not self.mouth_open_state
        mouth_value = 0.4 if self.mouth_open_state else 0.0
        self.set_mouth_open(mouth_value)
        
        state_text = "张开" if self.mouth_open_state else "关闭"
        
    def set_mouth_open(self, value):
        if self.model and hasattr(self.model, 'SetParameterValue'):
            try:
                self.model.SetParameterValue(StandardParams.ParamMouthOpenY, value, 1)
            except Exception as e:
                logger.error(f"[Live2D] 设置嘴巴参数失败: {e}")
                import traceback
                logger.error(f"[Debug] 详细错误信息: {traceback.format_exc()}")
        else:
            logger.warning(f"[Debug] 无法设置嘴巴参数 - model: {self.model}, hasSetParameterValue: {hasattr(self.model, 'SetParameterValue') if self.model else False}")

    def set_mouth_cycle_time(self, milliseconds):
        self.mouth_cycle_time = milliseconds
        if self.mouth_timer and self.mouth_control_enabled:
            self.mouth_timer.setInterval(milliseconds)
        
    @pyqtSlot(list)
    def on_expression_changed(self, expressions):
        logger.info(f"[Live2D] 收到表情变化: {expressions}")
        if self.model and expressions:
            for expression in expressions:
                try:
                    if hasattr(self.model, 'SetExpression'):
                        self.model.SetExpression(expression)
                        logger.info(f"[Live2D] 设置表情: {expression}")
                except Exception as e:
                    logger.error(f"[Live2D] 设置表情失败: {e}")

    def toggle_chat_window(self):
        if self.chat_window is None:
            self.chat_window = ChatFloatingWindow(self, self.controller)
            self.chat_window.window_closed.connect(self.on_chat_window_closed)
            
        if self.chat_window.isVisible():
            self.chat_window.hide()
        else:
            self.chat_window.show()
            self.chat_window.raise_()
            
    def on_chat_window_closed(self):
        self.chat_window = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        dialog_width = int(self.width() * 0.5)
        self.dialog_label.setFixedWidth(dialog_width)
        
        # 桌宠模式下调整按钮位置
        if self.window_mode == 2:
            size = self.width()
            self.close_button.move(size - 35, 5)
            self.minimize_button.move(size - 70, 5)

    def initializeGL(self):
        live2d.glewInit()
        
        # 启用混合和透明度
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        
        # 设置清除颜色为完全透明
        gl.glClearColor(0.0, 0.0, 0.0, 0.0)
        
        self.model = live2d.LAppModel()
        self.model.SetAutoBlinkEnable(True)
        self.model.SetAutoBreathEnable(True)

        # 尝试加载配置的模型文件
        model_loaded = False
        if config_manager:
            try:
                character_path = config_manager.get_character_path()
                if character_path and os.path.exists(character_path):
                    logger.info(f"正在加载配置的模型文件: {character_path}")
                    self.model.LoadModelJson(character_path)
                    model_loaded = True
                    logger.success(f"成功加载配置的模型: {character_path}")
                else:
                    logger.info("未找到配置的模型文件，将使用默认模型")
            except Exception as e:
                logger.error(f"加载配置模型失败: {e}")
        
        # 如果配置的模型加载失败，使用默认模型
        if not model_loaded:
            logger.info("使用默认模型")
            if live2d.LIVE2D_VERSION == 3:
                self.model.LoadModelJson("resources/v3/llny/llny.model3.json")
            else:
                self.model.LoadModelJson("resources/v2/haru/haru.model.json")

        # must be created after opengl context is configured
        self.canvas = Canvas()
        
        self.update_background()
        
        self.start_rendering()

    def start_rendering(self):
        if self.timer_id is None:
            self.is_rendering = True
            self.timer_id = self.startTimer(int(1000 / 60))

    def stop_rendering(self):
        if self.timer_id is not None:
            self.killTimer(self.timer_id)
            self.timer_id = None
            self.is_rendering = False
        self.stop_mouth_control()

    def show_settings(self):
        if self.stacked_widget:
            self.stop_rendering()
            self.stacked_widget.setCurrentIndex(1)

    def timerEvent(self, a0):
        if self.is_rendering:
            self.total_radius += self.radius_per_frame
            v = abs(math.cos(self.total_radius))
            self.update()

    def on_draw(self):
        # 清除缓冲区为透明
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        live2d.clearBuffer()
        
        # 桌宠模式下不绘制背景，保持透明
        if self.window_mode != 2 and self.background:
            self.background.Draw()
        elif self.window_mode != 2:  # 非桌宠模式但没有背景时使用白色
            gl.glClearColor(1.0, 1.0, 1.0, 1.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        # 桌宠模式保持透明，不做任何背景绘制
        
        # 应用人物控制变换到Live2D模型
        if self.model:
            # 使用Live2D模型的内置方法来设置缩放和偏移
            try:
                # 设置缩放
                if hasattr(self.model, 'SetScale'):
                    self.model.SetScale(self.character_scale)
                    logger.debug(f"[Live2D] 设置缩放: {self.character_scale}")
                
                # 设置偏移位置
                if hasattr(self.model, 'SetOffset'):
                    # 将滑块值转换为模型坐标
                    x_offset = self.character_x_offset / 100.0
                    y_offset = -self.character_y_offset / 100.0  # Y轴反向
                    self.model.SetOffset(x_offset, y_offset)
                    logger.debug(f"[Live2D] 设置偏移: ({x_offset}, {y_offset})")
                
            except Exception as e:
                logger.error(f"[Live2D] 设置变换失败: {e}")
            
            # 绘制模型
            self.model.Draw()
        else:
            logger.warning("[Live2D] 模型未初始化，无法绘制")

    def paintGL(self):
        # 确保背景透明
        gl.glClearColor(0.0, 0.0, 0.0, 0.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        
        self.model.Update()

        # render callback
        self.canvas.Draw(self.on_draw)

    def resizeGL(self, width: int, height: int):
        self.model.Resize(width, height)
        self.canvas.SetSize(width, height)

    @pyqtSlot(str)
    def show_dialog(self, text):
        """显示对话框，使用打字机效果逐字显示文本"""
        # 停止之前的打字机效果和隐藏定时器
        self.typewriter_timer.stop()
        self.dialog_hide_timer.stop()
        
        # 设置新的文本和重置索引
        self.typewriter_full_text = text
        self.typewriter_current_index = 0
        
        # 清空当前显示的文本并显示对话框
        self.dialog_label.setText("")
        self.dialog_label.show()
        
        # 开始打字机效果
        self.typewriter_timer.start(self.typewriter_speed)
        
        logger.info(f"[Live2D] 开始显示对话: {text[:50]}...")
    
    def reload_model(self):
        """重新加载模型"""
        try:
            if not config_manager:
                logger.warning("配置管理器不可用，无法重新加载模型")
                return False
                
            character_path = config_manager.get_character_path()
            if not character_path or not os.path.exists(character_path):
                logger.warning("未找到有效的模型文件路径")
                return False
            
            logger.info(f"正在重新加载模型: {character_path}")
            
            # 停止渲染
            was_rendering = self.is_rendering
            if was_rendering:
                self.stop_rendering()
            
            # 重新创建模型
            self.model = live2d.LAppModel()
            self.model.SetAutoBlinkEnable(True)
            self.model.SetAutoBreathEnable(True)
            
            # 加载新模型
            self.model.LoadModelJson(character_path)
            
            # 如果之前在渲染，重新开始渲染
            if was_rendering:
                self.start_rendering()
            
            logger.success(f"成功重新加载模型: {character_path}")
            return True
            
        except Exception as e:
            logger.error(f"重新加载模型失败: {e}")
            return False
    
    def update_typewriter_text(self):
        """更新打字机效果的文本显示"""
        if self.typewriter_current_index < len(self.typewriter_full_text):
            # 逐字添加文本
            current_text = self.typewriter_full_text[:self.typewriter_current_index + 1]
            self.dialog_label.setText(current_text)
            self.typewriter_current_index += 1
        else:
            # 打字完成，停止定时器并设置隐藏定时器
            self.typewriter_timer.stop()
            self.dialog_hide_timer.start(20000)  # 20秒后隐藏
            logger.info("[Live2D] 对话显示完成")
    
    def hide_dialog(self):
        """隐藏对话框"""
        self.dialog_label.hide()
        self.typewriter_timer.stop()
        self.dialog_hide_timer.stop()
        logger.info("[Live2D] 对话框已隐藏")
    
    def set_typewriter_speed(self, speed_ms):
        """设置打字机效果的速度
        
        Args:
            speed_ms (int): 每个字符显示的间隔时间（毫秒）
        """
        self.typewriter_speed = max(10, min(500, speed_ms))  # 限制在10-500ms之间
        logger.info(f"[Live2D] 打字机速度设置为: {self.typewriter_speed}ms")
    
    def stop_typewriter_effect(self):
        """停止打字机效果并立即显示完整文本"""
        if self.typewriter_timer.isActive():
            self.typewriter_timer.stop()
            self.dialog_label.setText(self.typewriter_full_text)
            self.dialog_hide_timer.start(20000)  # 20秒后隐藏
            logger.info("[Live2D] 打字机效果已停止，显示完整文本")
    
    def on_dialog_clicked(self, event):
        """对话框点击事件处理 - 跳过打字机效果"""
        if self.typewriter_timer.isActive():
            self.stop_typewriter_effect()
            logger.info("[Live2D] 用户点击对话框，跳过打字机效果")
        # 调用原始的鼠标事件处理
        QLabel.mousePressEvent(self.dialog_label, event)


class MainWindow(QWidget):
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OLV-QT")
        self.resize(800, 600)
        
        self.controller = None
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)  # 设置边距为0
        main_layout.setSpacing(0)  # 设置间距为0
        
        self.stacked_widget = QStackedWidget(self)
        self.stacked_widget.currentChanged.connect(self.on_page_changed)
        main_layout.addWidget(self.stacked_widget)

        self.live2d_page = None
        self.settings_page = QMLSettingsPage(self)

        self.setLayout(main_layout)
        
    async def initialize_backend(self):
        try:
            logger.info("正在初始化 WebSocket 控制器...")

            # 使用基于 WebSocket 的控制器取代旧后端
            ws_url = os.environ.get('OLV_WS_URL')
            base_url = os.environ.get('OLV_BASE_URL')
            self.controller = WSController(ws_url=ws_url, base_url=base_url)
            self.controller.connect_ws()

            self.live2d_page = Live2DCanvas(self.stacked_widget, self.controller, main_window=self)
            self.live2d_page.setStyleSheet("background: transparent;")

            # 连接背景设置信号
            if hasattr(self.settings_page, 'settings_slot'):
                self.live2d_page.setup_background_connections(self.settings_page.settings_slot)
                # 连接窗口模式设置信号
                self.live2d_page.setup_window_mode_connections(self.settings_page.settings_slot)
                # 连接模型设置信号，实现热重载
                self.settings_page.settings_slot.modelSettingsSaved.connect(self.on_model_settings_saved)

            self.stacked_widget.addWidget(self.live2d_page)
            self.stacked_widget.addWidget(self.settings_page)

            self.show_chat_window()

            logger.success("WebSocket 控制器初始化完成！")

        except Exception as e:
            logger.error(f"初始化 WebSocket 控制器失败: {e}")
            raise
            
    async def cleanup(self):
        # 断开 WebSocket 连接
        try:
            if hasattr(self, 'controller') and self.controller:
                disconnect = getattr(self.controller, 'disconnect_ws', None)
                if callable(disconnect):
                    disconnect()
        except Exception as e:
            logger.warning(f"断开 WebSocket 时出错: {e}")
        
        # 清理TTS音频缓存文件
        try:
            from OQConfig.cache_cleaner import clean_tts_cache
            success_count, failed_count = clean_tts_cache()
            if success_count > 0:
                logger.info(f"已清理 {success_count} 个TTS缓存文件")
        except Exception as e:
            logger.warning(f"清理TTS缓存文件时出错: {e}")
    
    async def reload_backend_config(self):
        """重新加载后端配置"""
        try:
            logger.info("正在重新加载应用配置...")
            # 使用统一配置管理器刷新当前配置选择
            if config_manager:
                config_manager.reload_config()
                logger.success("应用配置重新加载完成")
            else:
                logger.warning("配置管理器不可用，跳过配置重载")
        except Exception as e:
            logger.error(f"重新加载应用配置失败: {e}")
    
    def get_current_config_info(self):
        """获取当前配置信息"""
        try:
            if config_manager:
                selection = config_manager.get_current_selection()
                # 统一返回结构
                return {
                    'llm': selection.get('llm') or 'None',
                    'asr': selection.get('asr') or 'None',
                    'tts': selection.get('tts') or 'None',
                    'character': selection.get('character') or 'None',
                }
        except Exception as e:
            logger.warning(f"获取当前配置失败: {e}")
        return {'llm': 'None', 'asr': 'None', 'tts': 'None', 'character': 'None'}

    def add_chat_message(self, role: str, content: str, name: str = None):
        if hasattr(self.live2d_page, 'chat_window') and self.live2d_page.chat_window:
            self.live2d_page.chat_window.add_message(role, content, name)
            
    def show_chat_window(self):
        if hasattr(self.live2d_page, 'toggle_chat_window'):
            self.live2d_page.toggle_chat_window()

    def on_page_changed(self, index):
        if self.live2d_page:
            if index == 0:
                self.live2d_page.start_rendering()
            else:
                self.live2d_page.stop_rendering()
    
    @pyqtSlot()
    def on_model_settings_saved(self):
        """当模型设置保存时，重新加载模型"""
        try:
            logger.info("检测到模型设置已保存，正在重新加载模型...")
            if self.live2d_page and hasattr(self.live2d_page, 'reload_model'):
                success = self.live2d_page.reload_model()
                if success:
                    logger.success("模型热重载成功")
                else:
                    logger.warning("模型热重载失败")
            else:
                logger.warning("Live2D页面不可用，无法重新加载模型")
        except Exception as e:
            logger.error(f"模型热重载过程中发生错误: {e}")
